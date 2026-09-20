#!/usr/bin/env python3
"""OpenRecomp Phase-9 input/timer/event boundary gate (P9-07).

The gate proves the deterministic virtual-input and virtual-time boundary
(`.openrecomp-phase9/src/p9_input_timer_v1.py`):

* the public fixture's reachable controller read (`0x1f801040`) and timer 0
  counter read (`0x1f801100`) are discovered exactly and served by
  deterministic virtual interfaces (fixed button state; counter read returns
  the tick then advances);
* status/config reads and writes are recorded with explicitly labelled
  contract stubs; interrupt ports are classified but not modelled and become
  explicit blockers;
* out-of-range ports fail closed;
* the private Hercules reachable frontier is scanned with the same bounded
  discovery and its access set recorded; the fixture is never a `PASS`
  criterion and no payload bytes are recorded.

On success it emits::

    OPENRECOMP_P9_07=PASS
    OPENRECOMP_PHASE9_INPUT_TIMER_V1=PASS tests=<count>
    OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN
    OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN

Usage:

    python tools/test_phase9_input_timer_v1.py
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
import p9_input_timer_v1 as it  # noqa: E402
import p9_io_discovery_v1 as iod  # noqa: E402
import p9_memory_map_v1 as memory_map  # noqa: E402
import p9_psx_exe_v1 as psx  # noqa: E402
import p9_public_fixture_v1 as fixture  # noqa: E402

STAGE = "P9-07"
FEATURE_MARKER = "OPENRECOMP_PHASE9_INPUT_TIMER_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE9_HERCULES_PLAYABILITY"
NOT_PROVEN = "NOT_PROVEN"

DEFAULT_PRIVATE_FIXTURE = (
    ROOT.parents[1] / "fixtures" / "psx" / "hercules" / "SLUS_005.29"
)
PRIVATE_FIXTURE_LABEL = "hercules-slus-005.29"

RANGES = (
    iod.IoRange("joy", 0x1F801040, 0x10),
    iod.IoRange("timer0", 0x1F801100, 0x10),
    iod.IoRange("timer1", 0x1F801110, 0x10),
    iod.IoRange("timer2", 0x1F801120, 0x10),
    iod.IoRange("interrupt", 0x1F801070, 0x8),
)

PUBLIC_EXPECTED_ACCESSES = (
    ("0x80010030", "lw", "read", "0x1f801040", "joy"),
    ("0x80010048", "lw", "read", "0x1f801100", "timer0"),
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
        default=".openrecomp-phase9/evidence/P9-07",
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
        adapter = it.InputTimerAdapter()
        document = adapter.document()
        check("boundary:version", document["boundary_version"] == it.INPUT_TIMER_VERSION, document["boundary_version"])
        check("boundary:virtual-input-policy", document["virtual_input"]["policy"] == "fixed-deterministic-input-source", document["virtual_input"]["policy"])
        check("boundary:virtual-time-policy", document["virtual_time"]["policy"] == it.CLOCK_POLICY, document["virtual_time"]["policy"])
        check("boundary:interrupts-not-modelled", document["ports"]["interrupt"]["modelled"] is False, "not modelled")
        check("boundary:stub-policy", document["read_stubs"]["policy"] == it.STUB_POLICY, document["read_stubs"]["policy"])
        check("boundary:timer-ports", set(document["ports"]["timers"]) == {"timer0", "timer1", "timer2"}, json.dumps(sorted(document["ports"]["timers"]), sort_keys=True))

        # --- public fixture discovery ---------------------------------------
        public = analyze_bytes(fixture.build_fixture())
        discovery = iod.discover_accesses(public.analysis, RANGES)
        check("public:access-count", discovery["access_count"] == 2, str(discovery["access_count"]))
        observed = tuple(
            (item["site"], item["op"], item["direction"], item["address"], item["range"])
            for item in discovery["accesses"]
        )
        check("public:accesses", observed == PUBLIC_EXPECTED_ACCESSES, json.dumps(observed, sort_keys=True))

        # --- deterministic virtual interfaces -------------------------------
        for item in discovery["accesses"]:
            adapter.read(int(item["address"], 16), item["width_bits"])
        events = adapter.events
        check("public:event-count", len(events) == 2, str(len(events)))
        check("public:joy-event", events[0]["class"] == "VIRTUAL_INPUT" and events[0]["value"] == f"0x{it.VIRTUAL_INPUT_DEFAULT:08x}", json.dumps(events[0], sort_keys=True))
        check("public:timer-event", events[1]["class"] == "VIRTUAL_TIME" and events[1]["value"] == "0x00000000", json.dumps(events[1], sort_keys=True))
        check("public:ticks-advanced", adapter.ticks == 1, str(adapter.ticks))
        transcript = adapter.transcript_digest()
        replay = it.InputTimerAdapter()
        for item in discovery["accesses"]:
            replay.read(int(item["address"], 16), item["width_bits"])
        check("public:transcript-stable", replay.transcript_digest() == transcript, transcript)

        # --- timer reads advance deterministically --------------------------
        clock = it.InputTimerAdapter()
        values = [clock.read(it.TIMER_PORTS["timer0"][0], 16)["value"] for _ in range(3)]
        check("clock:sequence", values == ["0x00000000", "0x00000001", "0x00000002"], json.dumps(values))
        check("clock:ticks", clock.ticks == 3, str(clock.ticks))

        # --- interrupt blocker ----------------------------------------------
        interrupt = it.InputTimerAdapter()
        event = interrupt.read(it.I_STAT, 32)
        check("interrupt:blocker", event["class"] == "NOT_MODELLED" and event["blocker"] is True, json.dumps(event, sort_keys=True))
        check("interrupt:recorded", len(interrupt.blockers) == 1, str(len(interrupt.blockers)))
        write_event = interrupt.write(it.I_MASK, 32, 0)
        check("interrupt:write-blocker", write_event["blocker"] is True, json.dumps(write_event, sort_keys=True))

        # --- config writes and out-of-range ---------------------------------
        config = it.InputTimerAdapter()
        check("config:joy-ctrl", config.write(it.JOY_CTRL, 16, 0x0002)["class"] == "RECORDED_CONFIG", "joy-ctrl")
        check("config:timer-mode", config.write(it.TIMER_PORTS["timer1"][1], 16, 0x0001)["class"] == "RECORDED_CONFIG", "timer-mode")
        try:
            config.read(0x1F801010, 32)
            check("config:out-of-range", False, "expected NOT_AN_INPUT_TIMER_PORT")
        except it.InputTimerError as exc:
            check("config:out-of-range", exc.code == "NOT_AN_INPUT_TIMER_PORT", exc.code)

        public_record = {
            "schema": "openrecomp-phase9-input-timer-v1",
            "stage": STAGE,
            "fixture": fixture.PUBLIC_FIXTURE.label,
            "boundary": document,
            "discovery": discovery,
            "transcript_digest": transcript,
        }
        write_json(evidence / "public_input_timer.json", public_record)

        # --- private fixture scan -------------------------------------------
        fixture_path = pathlib.Path(options.private_fixture)
        private_record = {
            "schema": "openrecomp-phase9-private-input-timer-v1",
            "stage": STAGE,
            "label": PRIVATE_FIXTURE_LABEL,
            "present": fixture_path.is_file(),
            "is_pass_criterion": False,
            "boundary": document,
        }
        if fixture_path.is_file():
            private_bytes = fixture_path.read_bytes()
            private = analyze_bytes(private_bytes)
            private_discovery = iod.discover_accesses(private.analysis, RANGES)
            private_record["discovery"] = private_discovery
            private_record["note"] = "bounded same-block discovery over the reachable frontier; unresolved accesses are not guessed"
            private_text = json.dumps(private_record, sort_keys=True)
            assert_no_payload_leak("private:input-timer", private_text, psx.ingest(private_bytes).payload)
        write_json(evidence / "private_input_timer.json", private_record)
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
        "stage_name": "PS1 input/timer/event boundary",
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
    write_json(evidence / "p9_07_tests.json", record)

    for item in results:
        print(f"{item['status']}: {item['check']}")
    print(f"OPENRECOMP_P9_07={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(results)}")
    print(f"{TERMINAL_MARKER}={NOT_PROVEN}")
    print(f"{GENERAL_MARKER}={NOT_PROVEN}")
    print(f"{PLAYABILITY_MARKER}={NOT_PROVEN}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
