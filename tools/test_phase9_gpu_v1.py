#!/usr/bin/env python3
"""OpenRecomp Phase-9 PS1 GPU/runtime boundary gate (P9-06).

The gate proves the GPU platform adapter boundary
(`.openrecomp-phase9/src/p9_gpu_boundary_v1.py`) is explicit, deterministic
and non-emulating:

* the bounded port map (GP0/GP1 writes, GP0/GP1 reads) and documented coarse
  command-class tables are exact;
* the public fixture's reachable GPU accesses are discovered exactly (GP0
  `0xA0` CPU-to-VRAM copy, GP1 `0x00` reset) and recorded as a deterministic
  typed event transcript;
* unknown GPU commands become explicit unresolved blockers;
* GPU reads return explicitly labelled contract stubs;
* the private Hercules reachable frontier is scanned with the same bounded
  discovery and its (possibly empty) GPU access set is recorded; the fixture
  is never a `PASS` criterion and no payload bytes are recorded.

On success it emits::

    OPENRECOMP_P9_06=PASS
    OPENRECOMP_PHASE9_GPU_BOUNDARY_V1=PASS tests=<count>
    OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN
    OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN

Usage:

    python tools/test_phase9_gpu_v1.py
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

import p9_gpu_boundary_v1 as gpu  # noqa: E402
import p9_image_bridge_v1 as bridge  # noqa: E402
import p9_io_discovery_v1 as iod  # noqa: E402
import p9_memory_map_v1 as memory_map  # noqa: E402
import p9_psx_exe_v1 as psx  # noqa: E402
import p9_public_fixture_v1 as fixture  # noqa: E402

STAGE = "P9-06"
FEATURE_MARKER = "OPENRECOMP_PHASE9_GPU_BOUNDARY_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE9_HERCULES_PLAYABILITY"
NOT_PROVEN = "NOT_PROVEN"

DEFAULT_PRIVATE_FIXTURE = (
    ROOT.parents[1] / "fixtures" / "psx" / "hercules" / "SLUS_005.29"
)
PRIVATE_FIXTURE_LABEL = "hercules-slus-005.29"

GPU_RANGE = (iod.IoRange("gpu", 0x1F801810, 0x8),)

PUBLIC_EXPECTED_ACCESSES = (
    ("0x80010054", "sw", "0x1f801810", "0x000000a0"),
    ("0x8001005c", "sw", "0x1f801814", "0x00000000"),
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
        default=".openrecomp-phase9/evidence/P9-06",
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
        # --- boundary shape -------------------------------------------------
        adapter = gpu.GpuAdapter()
        document = adapter.document()
        check("boundary:no-emulation", document["emulation"] == "none-event-recording", document["emulation"])
        check("boundary:ports", set(document["ports"]) == {"0x1f801810", "0x1f801814"}, json.dumps(sorted(document["ports"]), sort_keys=True))
        check("boundary:gp0-class-count", len(document["gp0_command_classes"]) == 10, str(len(document["gp0_command_classes"])))
        check("boundary:gp1-class-count", len(document["gp1_command_classes"]) == 10, str(len(document["gp1_command_classes"])))
        check("boundary:stub-policy", document["read_stubs"]["policy"] == gpu.STUB_POLICY, document["read_stubs"]["policy"])

        # --- classification -------------------------------------------------
        gp0 = gpu.classify_gp0(0x000000A0)
        check("classify:gp0-nop", gp0["class"] == "NOP" and gp0["known"] is True, json.dumps(gp0, sort_keys=True))
        check("classify:gp0-nop-emulated", gp0["emulated"] is False, "not emulated")
        gp0_copy = gpu.classify_gp0(0xA0000000)
        check("classify:gp0-copy", gp0_copy["class"] == "CPU_TO_VRAM_COPY" and gp0_copy["known"] is True, json.dumps(gp0_copy, sort_keys=True))
        gp1 = gpu.classify_gp1(0x00000000)
        check("classify:gp1-00", gp1["class"] == "RESET_GPU" and gp1["known"] is True, json.dumps(gp1, sort_keys=True))
        unknown = gpu.classify_gp0(0x10000000)
        check("classify:gp0-unknown", unknown["class"] == "UNKNOWN_COMMAND" and unknown["known"] is False, json.dumps(unknown, sort_keys=True))

        # --- public fixture discovery and adapter transcript ----------------
        public = analyze_bytes(fixture.build_fixture())
        discovery = iod.discover_accesses(public.analysis, GPU_RANGE)
        check("public:access-count", discovery["access_count"] == 2, str(discovery["access_count"]))
        observed = tuple(
            (item["site"], item["op"], item["address"], item["value"]) for item in discovery["accesses"]
        )
        check("public:accesses", observed == PUBLIC_EXPECTED_ACCESSES, json.dumps(observed, sort_keys=True))
        for item in discovery["accesses"]:
            value = int(item["value"], 16)
            if item["address"] == "0x1f801810":
                adapter.write(0x1F801810, item["width_bits"], value)
            else:
                adapter.write(0x1F801814, item["width_bits"], value)
        check("public:events", adapter.write_count == 2 and adapter.read_count == 0, f"{adapter.write_count}/{adapter.read_count}")
        check("public:unknown-none", len(adapter.unknown_commands) == 0, str(len(adapter.unknown_commands)))
        check("public:event-classes", [event["class"] for event in adapter.events] == ["NOP", "RESET_GPU"], json.dumps([event["class"] for event in adapter.events]))
        transcript = adapter.transcript_digest()
        replay = gpu.GpuAdapter()
        for item in discovery["accesses"]:
            replay.write(int(item["address"], 16), item["width_bits"], int(item["value"], 16))
        check("public:transcript-stable", replay.transcript_digest() == transcript, transcript)

        # --- unknown command blocker ----------------------------------------
        unknown_adapter = gpu.GpuAdapter()
        unknown_event = unknown_adapter.write(gpu.GP0_WRITE, 32, 0x10000000)
        check("unknown:blocker", unknown_event["known"] is False and unknown_event["class"] == "UNKNOWN_COMMAND", json.dumps(unknown_event, sort_keys=True))
        check("unknown:recorded", len(unknown_adapter.unknown_commands) == 1, str(len(unknown_adapter.unknown_commands)))

        # --- read stubs -----------------------------------------------------
        read_adapter = gpu.GpuAdapter()
        gp1_read = read_adapter.read(gpu.GP1_READ, 32)
        check("read:gp1-stub", gp1_read["value"] == f"0x{gpu.GPUSTAT_STUB:08x}" and gp1_read["stub_policy"] == gpu.STUB_POLICY, json.dumps(gp1_read, sort_keys=True))
        gp0_read = read_adapter.read(gpu.GP0_READ, 32)
        check("read:gp0-stub", gp0_read["value"] == f"0x{gpu.GPUREAD_STUB:08x}", gp0_read["value"])
        check("read:count", read_adapter.read_count == 2, str(read_adapter.read_count))

        public_record = {
            "schema": "openrecomp-phase9-gpu-boundary-v1",
            "stage": STAGE,
            "fixture": fixture.PUBLIC_FIXTURE.label,
            "boundary": document,
            "discovery": discovery,
            "transcript_digest": transcript,
        }
        write_json(evidence / "public_gpu.json", public_record)

        # --- private fixture scan -------------------------------------------
        fixture_path = pathlib.Path(options.private_fixture)
        private_record = {
            "schema": "openrecomp-phase9-private-gpu-boundary-v1",
            "stage": STAGE,
            "label": PRIVATE_FIXTURE_LABEL,
            "present": fixture_path.is_file(),
            "is_pass_criterion": False,
            "boundary": document,
        }
        if fixture_path.is_file():
            private_bytes = fixture_path.read_bytes()
            private = analyze_bytes(private_bytes)
            private_discovery = iod.discover_accesses(private.analysis, GPU_RANGE)
            private_record["discovery"] = private_discovery
            private_record["note"] = "bounded same-block discovery over the reachable frontier; unresolved accesses are not guessed"
            private_text = json.dumps(private_record, sort_keys=True)
            assert_no_payload_leak("private:gpu", private_text, psx.ingest(private_bytes).payload)
        write_json(evidence / "private_gpu.json", private_record)
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
        "stage_name": "PS1 GPU/runtime boundary",
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
    write_json(evidence / "p9_06_tests.json", record)

    for item in results:
        print(f"{item['status']}: {item['check']}")
    print(f"OPENRECOMP_P9_06={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(results)}")
    print(f"{TERMINAL_MARKER}={NOT_PROVEN}")
    print(f"{GENERAL_MARKER}={NOT_PROVEN}")
    print(f"{PLAYABILITY_MARKER}={NOT_PROVEN}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
