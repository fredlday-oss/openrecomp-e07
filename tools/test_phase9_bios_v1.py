#!/usr/bin/env python3
"""OpenRecomp Phase-9 PS1 BIOS/service boundary gate (P9-05).

The gate proves the BIOS/service boundary
(`.openrecomp-phase9/src/p9_bios_boundary_v1.py`) is explicit, typed,
versioned and fail-closed:

* no BIOS image, BIOS code or firmware is used anywhere;
* the original public fixture reaches no BIOS/service call at all;
* an injected BIOS-style A0 table call is discovered as a candidate with an
  exact vector, and invoking it fails closed as unimplemented, as does any
  unknown service id;
* the private Hercules reachable indirect call sites are classified exactly
  (BIOS B0-table candidates versus memory-sourced unresolved targets) with no
  guessed resolution and no payload bytes in evidence; the fixture is never a
  `PASS` criterion.

On success it emits::

    OPENRECOMP_P9_05=PASS
    OPENRECOMP_PHASE9_BIOS_BOUNDARY_V1=PASS tests=<count>
    OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN
    OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN

Usage:

    python tools/test_phase9_bios_v1.py
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
import p9_memory_map_v1 as memory_map  # noqa: E402
import p9_psx_exe_v1 as psx  # noqa: E402
import p9_public_fixture_v1 as fixture  # noqa: E402
import psx_fixture_builder_v1 as builder  # noqa: E402

STAGE = "P9-05"
FEATURE_MARKER = "OPENRECOMP_PHASE9_BIOS_BOUNDARY_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE9_HERCULES_PLAYABILITY"
NOT_PROVEN = "NOT_PROVEN"

DEFAULT_PRIVATE_FIXTURE = (
    ROOT.parents[1] / "fixtures" / "psx" / "hercules" / "SLUS_005.29"
)
PRIVATE_FIXTURE_LABEL = "hercules-slus-005.29"

PRIVATE_EXPECTED_HISTOGRAM = {
    "BIOS_TABLE_CALL_CANDIDATE": 3,
    "INDIRECT_TARGET_UNKNOWN": 19,
}
PRIVATE_EXPECTED_CANDIDATE_SITES = ("0x80015fa4", "0x80026ebc", "0x80026f74")
PRIVATE_EXPECTED_CANDIDATE_VECTORS = ("B0", "B0", "B0")

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


def analyze_bytes(data: bytes) -> bridge.PipelineResult:
    image = psx.ingest(data)
    contract = memory_map.build_contract(image)
    flat = memory_map.flat_image(image)
    return bridge.analyze(image, contract, flat)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--evidence-dir",
        default=".openrecomp-phase9/evidence/P9-05",
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
        boundary = bios.default_boundary()
        document = boundary.as_dict()
        check("boundary:no-bios-image", document["bios_image"] == "none", document["bios_image"])
        check("boundary:fail-closed-policy", document["unknown_service_policy"] == "fail-closed", document["unknown_service_policy"])
        check(
            "boundary:recognized-unimplemented",
            len(document["services"]) == 3
            and all(service["category"] == "bios" and service["implemented"] is False for service in document["services"]),
            json.dumps(document["services"], sort_keys=True),
        )
        check(
            "boundary:vectors",
            document["vectors"] == {"A0": "0xa0", "B0": "0xb0", "C0": "0xc0"},
            json.dumps(document["vectors"], sort_keys=True),
        )
        try:
            boundary.resolve("bios-ZZ")
            check("boundary:unknown-service", False, "expected UNKNOWN_SERVICE")
        except bios.ServiceBoundaryError as exc:
            check("boundary:unknown-service", exc.code == "UNKNOWN_SERVICE", exc.code)

        # --- public fixture: no BIOS/service calls --------------------------
        public = analyze_bytes(fixture.build_fixture())
        public_discovery = bios.discover(public.analysis)
        check("public:no-sites", public_discovery["site_count"] == 0, str(public_discovery["site_count"]))
        check("public:no-candidates", public_discovery["bios_candidate_count"] == 0, str(public_discovery["bios_candidate_count"]))
        public_record = {
            "schema": "openrecomp-phase9-bios-boundary-public-v1",
            "stage": STAGE,
            "fixture": fixture.PUBLIC_FIXTURE.label,
            "boundary": document,
            "discovery": public_discovery,
            "requirement": "not-required-by-public-fixture",
        }
        write_json(evidence / "public_bios.json", public_record)

        # --- injected BIOS-style call is discovered and fails closed --------
        injected_words = list(fixture.build_words())
        bad_index = len(injected_words)
        injected_words += [
            builder.i_type("addiu", rt=2, rs=0, imm=0x00A0),
            builder.r_type("jalr", rs=2, rd=31),
            builder.nop(),
            builder.r_type("jr", rs=31),
            builder.nop(),
        ]
        injected_words[fixture.helper_call_index()] = builder.j_type("jal", fixture.PROGRAM_LOAD_ADDRESS + 4 * bad_index)
        injected = analyze_bytes(builder.build_from_words(injected_words))
        injected_discovery = bios.discover(injected.analysis)
        check("injected:candidate-count", injected_discovery["bios_candidate_count"] == 1, str(injected_discovery["bios_candidate_count"]))
        candidate = injected_discovery["bios_candidates"][0]
        check("injected:candidate-vector", candidate["vector"] == "A0", str(candidate.get("vector")))
        check("injected:candidate-class", candidate["class"] == "BIOS_TABLE_CALL_CANDIDATE", candidate["class"])
        try:
            boundary.invoke("bios-A0", ())
            check("injected:invoke-fails-closed", False, "expected UNIMPLEMENTED_SERVICE")
        except bios.ServiceBoundaryError as exc:
            check("injected:invoke-fails-closed", exc.code == "UNIMPLEMENTED_SERVICE", exc.code)

        # --- private fixture: exact classification --------------------------
        fixture_path = pathlib.Path(options.private_fixture)
        private_record = {
            "schema": "openrecomp-phase9-private-bios-boundary-v1",
            "stage": STAGE,
            "label": PRIVATE_FIXTURE_LABEL,
            "present": fixture_path.is_file(),
            "is_pass_criterion": False,
            "boundary": document,
        }
        if fixture_path.is_file():
            private_bytes = fixture_path.read_bytes()
            private = analyze_bytes(private_bytes)
            private_discovery = bios.discover(private.analysis)
            check("private:site-count", private_discovery["site_count"] == 22, str(private_discovery["site_count"]))
            check(
                "private:histogram",
                private_discovery["histogram"] == PRIVATE_EXPECTED_HISTOGRAM,
                json.dumps(private_discovery["histogram"], sort_keys=True),
            )
            check(
                "private:candidate-sites",
                tuple(item["site_hex"] if "site_hex" in item else f"0x{item['site']:08x}" for item in private_discovery["bios_candidates"]) == PRIVATE_EXPECTED_CANDIDATE_SITES,
                json.dumps([item["site"] for item in private_discovery["bios_candidates"]]),
            )
            check(
                "private:candidate-vectors",
                tuple(item["vector"] for item in private_discovery["bios_candidates"]) == PRIVATE_EXPECTED_CANDIDATE_VECTORS,
                json.dumps([item.get("vector") for item in private_discovery["bios_candidates"]]),
            )
            private_record["discovery"] = private_discovery
            private_record["first_unresolved_bios_site"] = "0x80015fa4"
            private_text = json.dumps(private_record, sort_keys=True)
            assert_no_payload_leak("private:bios", private_text, psx.ingest(private_bytes).payload)
        write_json(evidence / "private_bios.json", private_record)
        check("private:marker", True, "PRESENT" if fixture_path.is_file() else "ABSENT")
    except AssertionError as exc:
        RESULTS.append({"check": "gate:assertion", "status": "FAIL", "detail": str(exc)})
    except Exception as exc:  # fail closed with a stable record
        RESULTS.append({"check": "gate:exception", "status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"})

    failed = [item for item in RESULTS if item["status"] == "FAIL"]
    status = "PASS" if not failed else "FAIL"
    results = sorted(RESULTS, key=lambda item: item["check"])
    record = {
        "stage": STAGE,
        "stage_name": "PS1 BIOS/service boundary",
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
    write_json(evidence / "p9_05_tests.json", record)

    for item in results:
        print(f"{item['status']}: {item['check']}")
    print(f"OPENRECOMP_P9_05={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(results)}")
    print(f"{TERMINAL_MARKER}={NOT_PROVEN}")
    print(f"{GENERAL_MARKER}={NOT_PROVEN}")
    print(f"{PLAYABILITY_MARKER}={NOT_PROVEN}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
