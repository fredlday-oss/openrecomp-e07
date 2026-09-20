#!/usr/bin/env python3
"""OpenRecomp Phase-9 private Hercules bounded validation gate (P9-11).

The gate runs the private Hercules `SLUS_005.29` fixture through the complete
bounded Phase-9 path, stopping at the first unresolved blocker, and records
only non-reconstructive metadata:

* PS-X EXE ingestion identity (hashes, sizes, header fields);
* the explicit PS1 memory-map contract summary;
* the exact reachable frontier (counts, histograms, delay slots, control-flow
  counts) and the frozen pipeline result;
* the first unresolved blocker (`break` external trap at `0x80013390`) and the
  fail-closed structure error;
* the translation-closure classification of the reachable recognized-
  unsupported forms;
* the BIOS/service boundary classification (B0 candidates vs unknowns);
* the GPU/input/timer/SPU/CD-ROM reachable-access discovery counts;
* the bounded-execution status: `NOT_ATTEMPTED_BLOCKED_BY_FIRST_UNRESOLVED`,
  because the frozen pipeline fails closed before any translation, emission or
  native build of private code (which is never performed).

The private fixture is never a `PASS` criterion on its own, no payload bytes or
reconstructive derived data are committed, and private-fixture results never
promote the public claim or the permanent non-claims.

On success it emits::

    OPENRECOMP_P9_11=PASS
    OPENRECOMP_PHASE9_PRIVATE_VALIDATION_V1=PASS tests=<count>
    OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN
    OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN

Usage:

    python tools/test_phase9_hercules_v1.py
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / ".openrecomp-phase3" / "src"))
sys.path.insert(0, str(ROOT / ".openrecomp-phase8" / "src"))
sys.path.insert(0, str(ROOT / ".openrecomp-phase9" / "src"))
sys.path.insert(0, str(ROOT / ".openrecomp-phase9" / "fixture"))

import p9_bios_boundary_v1 as bios  # noqa: E402
import p9_image_bridge_v1 as bridge  # noqa: E402
import p9_io_discovery_v1 as iod  # noqa: E402
import p9_memory_map_v1 as memory_map  # noqa: E402
import p9_psx_exe_v1 as psx  # noqa: E402
import p9_semantics_v1 as semantics  # noqa: E402

STAGE = "P9-11"
FEATURE_MARKER = "OPENRECOMP_PHASE9_PRIVATE_VALIDATION_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE9_HERCULES_PLAYABILITY"
NOT_PROVEN = "NOT_PROVEN"

DEFAULT_PRIVATE_FIXTURE = (
    ROOT.parents[1] / "fixtures" / "psx" / "hercules" / "SLUS_005.29"
)
PRIVATE_FIXTURE_LABEL = "hercules-slus-005.29"

EXPECTED = {
    "file_sha256": "c230ff5cd14bdfa392f5d5765c9c907b631875aaaa7844792b38b9ac54930f6f",
    "payload_sha256": "2f48da4c642b25dd9d0b033f77b80a19e5befe34dc19da3194a51998e97c71be",
    "reachable_words": 4068,
    "reachable_supported_words": 3972,
    "reachable_unsupported_words": 96,
    "reachable_invalid_words": 0,
    "exception_site_count": 3,
    "first_blocker_site": "0x80013390",
    "first_blocker_kind": "external-trap",
    "first_blocker_op": "break",
    "structure_error_code": "CONTROL_WITHOUT_DELAY_SLOT",
    "bios_candidates": 3,
    "bios_unknown": 19,
}

IO_RANGES = (
    iod.IoRange("gpu", 0x1F801810, 0x8),
    iod.IoRange("joy", 0x1F801040, 0x10),
    iod.IoRange("timer0", 0x1F801100, 0x10),
    iod.IoRange("timer1", 0x1F801110, 0x10),
    iod.IoRange("timer2", 0x1F801120, 0x10),
    iod.IoRange("spu", 0x1F801C00, 0x400),
    iod.IoRange("cdrom", 0x1F801800, 0x4),
)

RESULTS: list[dict[str, str]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    RESULTS.append({"check": label, "status": "PASS" if condition else "FAIL", "detail": detail})
    if not condition:
        raise AssertionError(f"{label}: condition failed ({detail})")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def assert_no_payload_leak(label: str, text: str, payload: bytes) -> None:
    lowered = text.lower()
    sample = payload[:64]
    check(f"{label}:no-hex", sample.hex() not in lowered, "payload hex present")
    encoded = base64.b64encode(sample).decode("ascii")
    check(f"{label}:no-base64", encoded not in text, "payload base64 present")
    leaks = []
    for start in range(0, min(len(payload), 512)):
        run = payload[start : start + 8]
        if len(run) == 8 and all(32 <= byte < 127 for byte in run):
            if run.decode("ascii") in text:
                leaks.append(start)
                break
    check(f"{label}:no-ascii-run", not leaks, f"ascii payload run at {leaks[:1]}")
    for value in _string_values(json.loads(text)):
        check(f"{label}:string-length", len(value) <= 128, f"{len(value)} chars")


def _string_values(document):
    if isinstance(document, dict):
        for value in document.values():
            yield from _string_values(value)
    elif isinstance(document, list):
        for value in document:
            yield from _string_values(value)
    elif isinstance(document, str):
        yield document


def write_json(path: pathlib.Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--evidence-dir",
        default=".openrecomp-phase9/evidence/P9-11",
        help="evidence directory relative to the repository root",
    )
    parser.add_argument(
        "--private-fixture",
        default=os.environ.get("OPENRECOMP_PSX_PRIVATE_FIXTURE", str(DEFAULT_PRIVATE_FIXTURE)),
        help="optional local path to the private Hercules fixture",
    )
    options = parser.parse_args()
    evidence = (ROOT / options.evidence_dir).resolve()

    try:
        fixture_path = pathlib.Path(options.private_fixture)
        record = {
            "schema": "openrecomp-phase9-private-validation-v1",
            "stage": STAGE,
            "label": PRIVATE_FIXTURE_LABEL,
            "present": fixture_path.is_file(),
            "is_pass_criterion": False,
            "public_claim_promoted": False,
            "general_compatibility_promoted": False,
            "playability_promoted": False,
        }
        check("private:present", fixture_path.is_file(), "local private fixture present")
        if fixture_path.is_file():
            data = fixture_path.read_bytes()
            image = psx.ingest(data)
            identity = image.identity()
            check("private:file-sha256", identity["file_sha256"] == EXPECTED["file_sha256"], identity["file_sha256"])
            check("private:payload-sha256", identity["payload_sha256"] == EXPECTED["payload_sha256"], identity["payload_sha256"])

            contract = memory_map.build_contract(image)
            flat = memory_map.flat_image(image)
            pipeline = bridge.analyze(image, contract, flat)
            summary = pipeline.summary
            for key in (
                "reachable_words",
                "reachable_supported_words",
                "reachable_unsupported_words",
                "reachable_invalid_words",
                "exception_site_count",
            ):
                check(f"private:summary:{key}", summary[key] == EXPECTED[key], str(summary[key]))
            blocker = pipeline.first_blocker or {}
            check("private:blocker-site", blocker.get("site_hex") == EXPECTED["first_blocker_site"], str(blocker.get("site_hex")))
            check("private:blocker-kind", blocker.get("kind") == EXPECTED["first_blocker_kind"], str(blocker.get("kind")))
            check("private:blocker-op", blocker.get("op") == EXPECTED["first_blocker_op"], str(blocker.get("op")))
            check(
                "private:structure-fail-closed",
                (pipeline.structure_error or {}).get("code") == EXPECTED["structure_error_code"],
                str(pipeline.structure_error),
            )
            check("private:no-structure", pipeline.structure_summary is None, "no structure fabricated")

            unsupported = semantics.classify_reachable_unsupported(summary["unsupported_reachable_histogram"])
            check("private:unsupported-total", unsupported["total"] == 96, str(unsupported["total"]))
            check("private:unsupported-unknown", unsupported["unknown_ops"] == {}, json.dumps(unsupported["unknown_ops"], sort_keys=True))
            coprocessor = semantics.coprocessor_reachable(summary["reachable_op_histogram"])
            check("private:no-cop0-gte", coprocessor == {}, json.dumps(coprocessor, sort_keys=True))

            boundary = bios.default_boundary().as_dict()
            discovery = bios.discover(pipeline.analysis)
            check("private:bios-candidates", discovery["bios_candidate_count"] == EXPECTED["bios_candidates"], str(discovery["bios_candidate_count"]))
            check(
                "private:bios-unknown",
                discovery["histogram"].get("INDIRECT_TARGET_UNKNOWN") == EXPECTED["bios_unknown"],
                json.dumps(discovery["histogram"], sort_keys=True),
            )
            io = iod.discover_accesses(pipeline.analysis, IO_RANGES)
            check("private:io-accesses", io["access_count"] == 0, str(io["access_count"]))

            record.update(
                {
                    "identity": identity,
                    "contract_digest": memory_map.contract_digest(contract),
                    "frontier": {
                        "summary": summary,
                        "first_blocker": blocker,
                        "structure_error": pipeline.structure_error,
                        "pipeline_digest": pipeline.digest(),
                    },
                    "unsupported_classification": unsupported,
                    "coprocessor_reachable": coprocessor,
                    "bios_boundary": boundary,
                    "bios_discovery": discovery,
                    "io_discovery": io,
                    "bounded_execution": {
                        "status": "NOT_ATTEMPTED_BLOCKED_BY_FIRST_UNRESOLVED",
                        "reason": "frozen pipeline fails closed before translation, emission or native build of private code",
                        "first_blocker": blocker,
                        "native_execution_of_private_code": False,
                        "private_code_committed": False,
                    },
                }
            )
            record_text = json.dumps(record, sort_keys=True)
            assert_no_payload_leak("private:validation", record_text, image.payload)
        write_json(evidence / "private_validation.json", record)

        # The public claim and permanent non-claims must not be promoted here.
        check("claim:public-not-promoted", record["public_claim_promoted"] is False, "not promoted")
        check("claim:general-not-promoted", record["general_compatibility_promoted"] is False, "not promoted")
        check("claim:playability-not-promoted", record["playability_promoted"] is False, "not promoted")
    except AssertionError as exc:
        RESULTS.append({"check": "gate:assertion", "status": "FAIL", "detail": str(exc)})
    except Exception as exc:  # fail closed with a stable record
        RESULTS.append({"check": "gate:exception", "status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"})

    failed = [item for item in RESULTS if item["status"] == "FAIL"]
    status = "PASS" if not failed else "FAIL"
    results = sorted(RESULTS, key=lambda item: item["check"])
    record = {
        "stage": STAGE,
        "stage_name": "Private Hercules bounded validation",
        "status": status,
        "tests": len(results),
        "passed": sum(1 for item in results if item["status"] == "PASS"),
        "failed": len(failed),
        "private_fixture": {
            "label": PRIVATE_FIXTURE_LABEL,
            "present": pathlib.Path(options.private_fixture).is_file(),
            "is_pass_criterion": False,
        },
        "checks": results,
        "failure": None if not failed else [item["check"] for item in failed],
    }
    write_json(evidence / "p9_11_tests.json", record)

    for item in results:
        print(f"{item['status']}: {item['check']}")
    print(f"OPENRECOMP_P9_11={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(results)}")
    print(f"{TERMINAL_MARKER}={NOT_PROVEN}")
    print(f"{GENERAL_MARKER}={NOT_PROVEN}")
    print(f"{PLAYABILITY_MARKER}={NOT_PROVEN}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
