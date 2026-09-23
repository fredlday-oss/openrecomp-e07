#!/usr/bin/env python3
"""Deterministic P12-40 end-to-end replay gate.

Runs the bounded Hercules initialization from the fixture entry through the
B0 pad-patch sequence and to the current exact frontier, twice, captures stable
machine-readable deterministic state, and requires byte-identical replay
evidence. Intentionally nondeterministic metadata is excluded.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase3/src", ".openrecomp-phase8/src",
              ".openrecomp-phase9/src", ".openrecomp-phase9/fixture",
              ".openrecomp-phase10/src", ".openrecomp-phase11/src",
              ".openrecomp-phase12/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p12_proof_v1 as proof  # noqa: E402
from tools import test_phase11_gpu_v1 as p11_05  # noqa: E402
from tools import test_phase12_caller_coverage_v1 as cov  # noqa: E402

STAGE = "P12-40"
INITIALIZATION_MARKER = "OPENRECOMP_PHASE12_HERCULES_INITIALIZATION_PROOF"
FRAME_MARKER = "OPENRECOMP_PHASE12_HERCULES_FRAME_PROOF"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE12_HERCULES_PLAYABILITY_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE12_GENERAL_PS1_COMPATIBILITY"
REPLAY_MARKER = "OPENRECOMP_PHASE12_END_TO_END_REPLAY_V1"

RESULTS: list[dict[str, str]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    RESULTS.append({"check": label, "status": "PASS" if condition else "FAIL",
                    "detail": detail})
    if not condition:
        raise AssertionError(f"{label}: condition failed ({detail})")


def write_json(path: pathlib.Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def digest(document: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(document, sort_keys=True).encode("utf-8")
    ).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=".openrecomp-phase12/evidence/P12-40")
    parser.add_argument("--private-fixture-root",
                        default=str(p11_05.DEFAULT_PRIVATE_FIXTURE_ROOT))
    options = parser.parse_args()
    evidence = (ROOT / options.evidence_dir).resolve()
    build_root = ROOT / ".openrecomp-phase12" / "build"

    try:
        result = proof.build_and_run(build_root, "p12-40-replay",
                                     fixture_root=pathlib.Path(options.private_fixture_root))
        first = result["first"]
        second = result["second"]
        check("run:build", all(status == "OK" for status in result["built"]["build_status"]),
              str(result["built"]["build_status"]))
        check("run:exit-stderr",
              first["returncode"] == second["returncode"] == 0
              and first["stderr_bytes"] == second["stderr_bytes"] == 0,
              "exit 0 and empty stderr")

        fields_first = proof.deterministic_fields(first, second)
        fields_second = {
            key: second["simple"].get(key, "")
            for key in proof.DETERMINISTIC_OBSERVABLE_KEYS
        }
        check("replay:deterministic-fields-identical",
              fields_first == fields_second,
              digest(fields_first))
        check("replay:stdout-byte-identical",
              first["stdout"] == second["stdout"], first["stdout_sha256"])

        replay = {
            "schema": "openrecomp-phase12-end-to-end-replay-v1",
            "stage": STAGE,
            "result": "PASS",
            "deterministic_fields": fields_first,
            "replay_digest": digest(fields_first),
            "run1": {
                "stdout_sha256": first["stdout_sha256"],
                "replay_digest": digest(fields_first),
            },
            "run2": {
                "stdout_sha256": second["stdout_sha256"],
                "replay_digest": digest(fields_second),
            },
            "byte_identical": first["stdout"] == second["stdout"],
            "excluded_nondeterministic": ["host paths", "timestamps", "process identity"],
        }
        write_json(evidence / "replay.json", replay)
        cov.assert_public_safe("replay", replay, result["image"].payload)

        tests = {
            "schema": "openrecomp-phase12-tests-v1",
            "stage": STAGE,
            "checks": RESULTS,
            "summary": {"passed": len(RESULTS), "failed": 0},
        }
        write_json(evidence / "p12_40_tests.json", tests)
        write_json(evidence / "RESULT.json", {
            "schema": "openrecomp-phase12-result-v1",
            "stage": STAGE,
            "status": "PASS",
            "markers": {
                "OPENRECOMP_P12_40": "PASS",
                REPLAY_MARKER: "PASS",
                INITIALIZATION_MARKER: "NOT_PROVEN",
                FRAME_MARKER: "NOT_PROVEN",
                PLAYABILITY_MARKER: "NOT_PROVEN",
                GENERAL_MARKER: "NOT_PROVEN",
            },
            "next_stage": "P12-90",
        })

        for item in RESULTS:
            detail = f" {item['detail']}" if item["detail"] else ""
            print(f"{item['status']}: {item['check']}{detail}")
        print("OPENRECOMP_P12_40=PASS")
        print(f"{REPLAY_MARKER}=PASS")
        print(f"{INITIALIZATION_MARKER}=NOT_PROVEN")
        print(f"{FRAME_MARKER}=NOT_PROVEN")
        print(f"{PLAYABILITY_MARKER}=NOT_PROVEN")
        print(f"{GENERAL_MARKER}=NOT_PROVEN")
        print(f"P12_40_CHECKS={len(RESULTS)}")
        return 0
    except AssertionError as exc:
        print(f"FAIL: p12-40:{exc}")
        return 1
    except Exception as exc:
        print(f"FAIL: p12-40:{type(exc).__name__}:{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
