#!/usr/bin/env python3
"""OpenRecomp Phase-10 dynamic PS1 I/O discovery gate (P10-06).

Phase 9 found zero statically discoverable I/O-range accesses. This gate
classifies the device transitions that actually occurred during the
deterministic `P10-05` native Hercules run and, independently, re-runs the
constant-base scan over the reachable program:

* the audited Phase-9 port ranges are reused unchanged (no invented device
  map);
* the static scan classifies reachable memory accesses whose base register is a
  constant, and keeps unresolved bases explicit;
* the dynamic record classifies the observed GPU / controller / SPU / CD-ROM
  event categories and the denied accesses, whose address is explicitly not
  observable;
* no device is extended at this stage: the observed classes are already served
  by the Phase-9 typed port boundary and unknown ports/commands stay
  fail-closed.

On success it emits::

    OPENRECOMP_P10_06=PASS
    OPENRECOMP_PHASE10_IO_DISCOVERY_V1=PASS tests=<count>
    OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE10_HERCULES_PLAYABILITY=NOT_PROVEN
    OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase10_io_v1.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase3/src", ".openrecomp-phase8/src",
              ".openrecomp-phase9/src", ".openrecomp-phase10/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p9_image_bridge_v1 as bridge  # noqa: E402
import p9_memory_map_v1 as memory_map  # noqa: E402
import p9_psx_exe_v1 as psx  # noqa: E402
import p10_io_discovery_v1 as io  # noqa: E402

STAGE = "P10-06"
FEATURE_MARKER = "OPENRECOMP_PHASE10_IO_DISCOVERY_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE10_HERCULES_PLAYABILITY"
GENERAL_MARKER = "OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY"
NOT_PROVEN = "NOT_PROVEN"

P10_05_RECORD = ".openrecomp-phase10/evidence/P10-05/native_entry.json"
P10_05_RECORD_SHA256 = "ef7b834293e4e5ff1067c78154ccbbeac218276bea1375000bd380e3cb6c05e9"

EXPECTED = {
    "access_sites": 1107,
    "unresolved_base": 769,
    "outside_audited": 338,
    "audited_device_sites": 0,
    "observed_devices": ["gpu", "input", "spu", "cdrom"],
    "required_devices_sorted": ["cdrom", "gpu", "input", "spu"],
    "denied": 11,
    "termination": "UNRESOLVED_INDIRECT_JUMP",
    "budget_reached": True,
}

RESULTS: list[dict[str, str]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    RESULTS.append({"check": label, "status": "PASS" if condition else "FAIL", "detail": detail})
    if not condition:
        raise AssertionError(f"{label}: condition failed ({detail})")


def write_json(path: pathlib.Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=".openrecomp-phase10/evidence/P10-06")
    parser.add_argument("--private-fixture",
                        default=str(ROOT.parents[1] / "fixtures" / "psx" / "hercules" / "SLUS_005.29"))
    args = parser.parse_args()
    evidence = (ROOT / args.evidence_dir).resolve()
    private_path = pathlib.Path(args.private_fixture)

    try:
        # --- dynamic source: the deterministic P10-05 native record -----------
        record_path = ROOT / P10_05_RECORD
        check("dynamic:record-present", record_path.is_file(), P10_05_RECORD)
        record_bytes = record_path.read_bytes()
        check(
            "dynamic:record-identity",
            hashlib.sha256(record_bytes).hexdigest() == P10_05_RECORD_SHA256,
            hashlib.sha256(record_bytes).hexdigest(),
        )
        native_record = json.loads(record_bytes.decode("utf-8"))
        dynamic = io.classify_dynamic(native_record)
        check("dynamic:observed-count", dynamic["observed_device_count"] == 4, str(dynamic["observed_device_count"]))
        check(
            "dynamic:observed-devices",
            [item["device"] for item in dynamic["observed_devices"]] == EXPECTED["observed_devices"],
            ",".join(item["device"] for item in dynamic["observed_devices"]),
        )
        check("dynamic:denied", dynamic["denied_accesses"] == EXPECTED["denied"], str(dynamic["denied_accesses"]))
        check("dynamic:denied-not-observable", dynamic["denied_address_observable"] is False, "false")
        check("dynamic:termination", dynamic["termination_category"] == EXPECTED["termination"], str(dynamic["termination_category"]))
        check("dynamic:budget-reached", dynamic["budget_reached"] is True, "true")
        check("dynamic:host-services", dynamic["host_service_calls"] > 0, str(dynamic["host_service_calls"]))
        check(
            "dynamic:unmodelled-policy",
            dynamic["unmodelled_device_policy"] == "fail-closed",
            dynamic["unmodelled_device_policy"],
        )
        check(
            "dynamic:uncapped-devices",
            {item["device"] for item in dynamic["observed_devices"] if not item["capped"]} == {"spu", "cdrom"},
            str([item["device"] for item in dynamic["observed_devices"] if not item["capped"]]),
        )

        # --- static source: constant-base scan over the reachable program -----
        check("private:present", private_path.is_file(), "private fixture present")
        image = psx.ingest(private_path.read_bytes())
        contract = memory_map.build_contract(image)
        flat = memory_map.flat_image(image)
        pipeline = bridge.analyze(image, contract, flat)
        static = io.discover_constant_accesses(pipeline.analysis)
        check("static:access-sites", static["access_site_count"] == EXPECTED["access_sites"], str(static["access_site_count"]))
        check(
            "static:histogram",
            static["histogram"]
            == {io.CLASS_OUTSIDE_AUDITED: EXPECTED["outside_audited"],
                io.CLASS_UNRESOLVED_BASE: EXPECTED["unresolved_base"]},
            json.dumps(static["histogram"], sort_keys=True),
        )
        check(
            "static:no-audited-device-sites",
            static["device_histogram"] == {} and static["first_device_site"] is None,
            json.dumps(static["device_histogram"], sort_keys=True),
        )
        observed_addresses = sorted(
            int(site["address"], 16) for site in static["sites"] if site.get("address")
        )
        check(
            "static:resolved-addresses-are-ram",
            all(0x80000000 <= address < 0x80200000 for address in observed_addresses),
            f"{len(observed_addresses)} resolved addresses",
        )
        check(
            "static:unresolved-have-evidence",
            all(
                site.get("evidence")
                for site in static["sites"]
                if site["classification"] == io.CLASS_UNRESOLVED_BASE
            ),
            "every unresolved base carries slice evidence",
        )
        check(
            "static:audited-ranges",
            len(static["audited_ranges"]) == 8,
            str(len(static["audited_ranges"])),
        )
        check(
            "static:residual-policy",
            "fail closed" in static["residual_policy"],
            static["residual_policy"],
        )

        # --- requirements -----------------------------------------------------
        requirement_record = io.requirements(static, dynamic)
        check(
            "requirements:dynamically-required",
            requirement_record["dynamically_required_devices"] == EXPECTED["required_devices_sorted"],
            ",".join(requirement_record["dynamically_required_devices"]),
        )
        check(
            "requirements:no-new-implementation",
            requirement_record["implemented_at_phase10"] == [],
            "none",
        )
        check(
            "requirements:served-by-phase9",
            requirement_record["already_implemented_by_phase9"] == EXPECTED["required_devices_sorted"],
            ",".join(requirement_record["already_implemented_by_phase9"]),
        )
        check(
            "requirements:not-speculative",
            set(requirement_record["not_required_and_not_implemented"]) == {"dma", "memory_control", "expansion", "sio"},
            ",".join(requirement_record["not_required_and_not_implemented"]),
        )

        write_json(
            evidence / "io_discovery.json",
            {
                "schema": "openrecomp-phase10-io-discovery-v1",
                "stage": STAGE,
                "label": "hercules-private-fixture",
                "is_pass_criterion": False,
                "dynamic_source": {"record": P10_05_RECORD, "sha256": P10_05_RECORD_SHA256},
                "dynamic": dynamic,
                "static": {
                    key: value for key, value in static.items() if key != "sites"
                },
                "static_sites_sha256": hashlib.sha256(
                    json.dumps(static["sites"], sort_keys=True).encode("utf-8")
                ).hexdigest(),
                "requirements": requirement_record,
            },
        )

        check("claim:native-execution-not-promoted", True, NOT_PROVEN)
        check("claim:playability-not-promoted", True, NOT_PROVEN)
        check("claim:general-not-promoted", True, NOT_PROVEN)
    except AssertionError as exc:
        RESULTS.append({"check": "gate:assertion", "status": "FAIL", "detail": str(exc)})
    except Exception as exc:  # fail closed with a stable record
        RESULTS.append({"check": "gate:exception", "status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"})

    failed = [item for item in RESULTS if item["status"] == "FAIL"]
    status = "PASS" if not failed else "FAIL"
    results = sorted(RESULTS, key=lambda item: item["check"])
    stage_record = {
        "stage": STAGE,
        "stage_name": "Dynamic PS1 I/O discovery",
        "status": status,
        "tests": len(results),
        "passed": sum(1 for item in results if item["status"] == "PASS"),
        "failed": len(failed),
        "checks": results,
        "failure": None if not failed else [item["check"] for item in failed],
    }
    write_json(evidence / "p10_06_tests.json", stage_record)

    for item in results:
        print(f"{item['status']}: {item['check']}")
    print(f"OPENRECOMP_P10_06={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(results)}")
    print(f"{TERMINAL_MARKER}={NOT_PROVEN}")
    print(f"{PLAYABILITY_MARKER}={NOT_PROVEN}")
    print(f"{GENERAL_MARKER}={NOT_PROVEN}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
