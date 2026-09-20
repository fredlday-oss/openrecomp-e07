#!/usr/bin/env python3
"""OpenRecomp Phase-9 PS1 SPU/audio boundary gate (P9-08).

The gate proves the SPU/audio platform boundary
(`.openrecomp-phase9/src/p9_spu_boundary_v1.py`) is explicit, deterministic,
non-synthesising and fail-closed:

* the bounded SPU register ranges and named control registers are exact;
* the public fixture's reachable SPU write (SPUCNT low byte `0xc0` at
  `0x1f801daa`) is discovered exactly and recorded as a typed event;
* unknown SPU registers become explicit blockers and out-of-range ports fail
  closed;
* the private Hercules reachable frontier is scanned with the same bounded
  discovery and its access set recorded; the fixture is never a `PASS`
  criterion and no payload bytes are recorded.

On success it emits::

    OPENRECOMP_P9_08=PASS
    OPENRECOMP_PHASE9_SPU_BOUNDARY_V1=PASS tests=<count>
    OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN
    OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN

Usage:

    python tools/test_phase9_spu_v1.py
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

import p9_image_bridge_v1 as bridge  # noqa: E402
import p9_io_discovery_v1 as iod  # noqa: E402
import p9_memory_map_v1 as memory_map  # noqa: E402
import p9_psx_exe_v1 as psx  # noqa: E402
import p9_public_fixture_v1 as fixture  # noqa: E402
import p9_spu_boundary_v1 as spu  # noqa: E402

STAGE = "P9-08"
FEATURE_MARKER = "OPENRECOMP_PHASE9_SPU_BOUNDARY_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE9_HERCULES_PLAYABILITY"
NOT_PROVEN = "NOT_PROVEN"

DEFAULT_PRIVATE_FIXTURE = (
    ROOT.parents[1] / "fixtures" / "psx" / "hercules" / "SLUS_005.29"
)
PRIVATE_FIXTURE_LABEL = "hercules-slus-005.29"

SPU_RANGE = (iod.IoRange("spu", spu.SPU_BASE, spu.SPU_SIZE),)

PUBLIC_EXPECTED_ACCESSES = (
    ("0x80010074", "sb", "write", "0x1f801daa", "0x000000c0"),
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


def analyze_bytes(data: bytes) -> bridge.PipelineResult:
    image = psx.ingest(data)
    contract = memory_map.build_contract(image)
    flat = memory_map.flat_image(image)
    return bridge.analyze(image, contract, flat)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--evidence-dir",
        default=".openrecomp-phase9/evidence/P9-08",
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
        adapter = spu.SpuAdapter()
        document = adapter.document()
        check("boundary:no-emulation", document["emulation"] == "none-event-recording", document["emulation"])
        check("boundary:no-synthesis", document["audio_synthesis"] == "none", document["audio_synthesis"])
        check("boundary:ranges", document["ranges"]["voices"] == "0x1f801c00+384", document["ranges"]["voices"])
        check("boundary:named-registers", len(document["named_registers"]) == 21, str(len(document["named_registers"])))
        check("boundary:stub-policy", document["read_stubs"]["policy"] == spu.STUB_POLICY, document["read_stubs"]["policy"])

        # --- public fixture discovery ---------------------------------------
        public = analyze_bytes(fixture.build_fixture())
        discovery = iod.discover_accesses(public.analysis, SPU_RANGE)
        check("public:access-count", discovery["access_count"] == 1, str(discovery["access_count"]))
        observed = tuple(
            (item["site"], item["op"], item["direction"], item["address"], item["value"])
            for item in discovery["accesses"]
        )
        check("public:accesses", observed == PUBLIC_EXPECTED_ACCESSES, json.dumps(observed, sort_keys=True))

        item = discovery["accesses"][0]
        event = adapter.write(int(item["address"], 16), item["width_bits"], int(item["value"], 16))
        check("public:event-register", event["register"] == "SPU_CONTROL", event["register"])
        check("public:event-category", event["category"] == "CONTROL_REGISTER", event["category"])
        check("public:event-value", event["value"] == "0x000000c0", event["value"])
        check("public:event-not-blocker", event["blocker"] is False, "not blocker")
        transcript = adapter.transcript_digest()
        replay = spu.SpuAdapter()
        replay.write(int(item["address"], 16), item["width_bits"], int(item["value"], 16))
        check("public:transcript-stable", replay.transcript_digest() == transcript, transcript)

        # --- classification and fail-closed behaviour -----------------------
        check("classify:voice", spu.classify(0x1F801C10) == "VOICE_REGISTER", spu.classify(0x1F801C10))
        check("classify:transfer", spu.classify(0x1F801DA8) == "TRANSFER_REGISTER", spu.classify(0x1F801DA8))
        check("classify:unknown", spu.classify(0x1F801DC0) == "UNKNOWN_SPU_REGISTER", spu.classify(0x1F801DC0))
        unknown = adapter.write(0x1F801DC0, 16, 0x0001)
        check("unknown:blocker", unknown["blocker"] is True, json.dumps(unknown, sort_keys=True))
        check("unknown:recorded", len(adapter.blockers) == 1, str(len(adapter.blockers)))
        read_event = spu.SpuAdapter().read(0x1F801DAE, 16)
        check("read:stub", read_event["value"] == "0x00000000" and read_event["stub_policy"] == spu.STUB_POLICY, json.dumps(read_event, sort_keys=True))
        try:
            spu.SpuAdapter().write(0x1F801BFF, 16, 0)
            check("out-of-range", False, "expected NOT_AN_SPU_PORT")
        except spu.SpuBoundaryError as exc:
            check("out-of-range", exc.code == "NOT_AN_SPU_PORT", exc.code)

        public_record = {
            "schema": "openrecomp-phase9-spu-boundary-v1",
            "stage": STAGE,
            "fixture": fixture.PUBLIC_FIXTURE.label,
            "boundary": document,
            "discovery": discovery,
            "transcript_digest": transcript,
        }
        write_json(evidence / "public_spu.json", public_record)

        # --- private fixture scan -------------------------------------------
        fixture_path = pathlib.Path(options.private_fixture)
        private_record = {
            "schema": "openrecomp-phase9-private-spu-boundary-v1",
            "stage": STAGE,
            "label": PRIVATE_FIXTURE_LABEL,
            "present": fixture_path.is_file(),
            "is_pass_criterion": False,
            "boundary": document,
        }
        if fixture_path.is_file():
            private_bytes = fixture_path.read_bytes()
            private = analyze_bytes(private_bytes)
            private_discovery = iod.discover_accesses(private.analysis, SPU_RANGE)
            private_record["discovery"] = private_discovery
            private_record["note"] = "bounded same-block discovery over the reachable frontier; unresolved accesses are not guessed"
            private_text = json.dumps(private_record, sort_keys=True)
            assert_no_payload_leak("private:spu", private_text, psx.ingest(private_bytes).payload)
        write_json(evidence / "private_spu.json", private_record)
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
        "stage_name": "PS1 SPU/audio boundary",
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
    write_json(evidence / "p9_08_tests.json", record)

    for item in results:
        print(f"{item['status']}: {item['check']}")
    print(f"OPENRECOMP_P9_08={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(results)}")
    print(f"{TERMINAL_MARKER}={NOT_PROVEN}")
    print(f"{GENERAL_MARKER}={NOT_PROVEN}")
    print(f"{PLAYABILITY_MARKER}={NOT_PROVEN}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
