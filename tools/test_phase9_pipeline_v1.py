#!/usr/bin/env python3
"""OpenRecomp Phase-9 MIPS32 pipeline integration gate (P9-03).

The gate proves the PS1-to-MIPS32 bridge
(`.openrecomp-phase9/src/p9_image_bridge_v1.py`) drives a validated PS-X EXE
through the existing frozen Phase-8 MIPS32 pipeline without forking it:

* the original public fixture reaches a complete, deterministic neutral
  structure (ProgramModel / CFG / functions / call graph / translation units)
  with exact pinned counts and fingerprints;
* the reused Phase-3/Phase-8 modules hash-equal their frozen manifest entries;
* an injected indirect call fails closed as an unresolved site;
* the private Hercules fixture frontier is characterized exactly (counts,
  histograms, first blocker) and the structure bridge fails closed at the
  first unsupported control transfer; only non-reconstructive metadata is
  recorded and it is never a `PASS` criterion.

On success it emits::

    OPENRECOMP_P9_03=PASS
    OPENRECOMP_PHASE9_PIPELINE_V1=PASS tests=<count>
    OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN
    OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN

Usage:

    python tools/test_phase9_pipeline_v1.py
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
import p9_memory_map_v1 as memory_map  # noqa: E402
import p9_psx_exe_v1 as psx  # noqa: E402
import p9_public_fixture_v1 as fixture  # noqa: E402
import psx_fixture_builder_v1 as builder  # noqa: E402

STAGE = "P9-03"
FEATURE_MARKER = "OPENRECOMP_PHASE9_PIPELINE_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE9_HERCULES_PLAYABILITY"
NOT_PROVEN = "NOT_PROVEN"

DEFAULT_PRIVATE_FIXTURE = (
    ROOT.parents[1] / "fixtures" / "psx" / "hercules" / "SLUS_005.29"
)
PRIVATE_FIXTURE_LABEL = "hercules-slus-005.29"

FROZEN_MODULE_HASHES = {
    ".openrecomp-phase3/src/p3_code_frontier_v1.py":
        "f02c4e7507087e052f1a899ef67d87f8ed82ecc4954e8214ccea922a2e361d71",
    ".openrecomp-phase3/src/p3_decode_mips32_v1.py":
        "c808a23afad5771a42f3f7eee9450b84fc6131d0416961a3ed8e78a9f5126b0b",
    ".openrecomp-phase8/src/p8_structure_v1.py":
        "24109660cfa1876b9ffabe141374d1a1b26c74d6fc0f68260bfb440617077a1b",
}

PUBLIC_EXPECTED = {
    "total_words": 46,
    "reachable_words": 46,
    "reachable_supported_words": 46,
    "reachable_unsupported_words": 0,
    "reachable_invalid_words": 0,
    "unreachable_words": 0,
    "delay_slot_count": 7,
    "non_nop_delay_slot_count": 0,
    "exception_site_count": 0,
    "control_flow_site_counts": {
        "conditional-branches": 2,
        "direct-calls": 2,
        "indirect-calls": 0,
        "indirect-jumps": 0,
        "jumps": 0,
        "returns": 3,
        "unsupported-control-transfers": 0,
    },
    "unresolved_site_counts": {},
    "neutral_instructions": 39,
    "folded_delay_slots": 7,
    "blocks": 9,
    "edges": 8,
    "functions": 3,
    "call_edges_internal": 2,
    "call_edges_external": 0,
    "call_edges_unresolved": 0,
    "translation_units": 3,
    "entry_function": "fn_80010000",
    "entry_unit": "tu_fn_80010000",
    "unowned_blocks": 0,
    "shared_blocks": 0,
    "program_model_fingerprint": "99024c485f3203cc1701a045758a371538754bd7fe2c0193066f735a2adafa3d",
    "cfg_fingerprint": "e35974b4e423ad3fa4fad4b44844e7f525ac776b51e1e072156d62b504310ea4",
    "call_graph_fingerprint": "542d69e7913851e463a62c043b31f4156ddad5179ecb2f99885ec7d207d4a760",
    "units_fingerprint": "aa5614f991f3b8dd867f45c86a1559cf87bba6bd9f51e6d2274bdd6407e8fa02",
    "discovery_fingerprint": "fff9df3a03a6dd2bb69fdeea9df0c31076bb4c0a2c80ac0891f005d46e6f9b6a",
}

PRIVATE_EXPECTED = {
    "reachable_words": 4068,
    "reachable_supported_words": 3972,
    "reachable_unsupported_words": 96,
    "reachable_invalid_words": 0,
    "unresolved_site_counts": {"external-trap": 3, "indirect-call": 22, "indirect-jump": 18},
    "exception_site_count": 3,
    "first_blocker_site": "0x80013390",
    "first_blocker_kind": "external-trap",
    "first_blocker_op": "break",
    "structure_error_code": "CONTROL_WITHOUT_DELAY_SLOT",
}

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
        default=".openrecomp-phase9/evidence/P9-03",
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
        # --- reuse: frozen modules unchanged -------------------------------
        for rel, expected in sorted(FROZEN_MODULE_HASHES.items()):
            check(f"reuse:module:{rel}", sha256((ROOT / rel).read_bytes()) == expected, expected)

        # --- public fixture through the frozen pipeline --------------------
        public_bytes = fixture.build_fixture()
        public_image = psx.ingest(public_bytes)
        public_contract = memory_map.build_contract(public_image)
        public_flat = memory_map.flat_image(public_image)
        public = bridge.analyze(public_image, public_contract, public_flat)
        check("public:no-structure-error", public.structure_error is None, str(public.structure_error))
        check("public:no-blocker", public.first_blocker is None, str(public.first_blocker))
        check("public:structure-built", public.structure_summary is not None, "structure")
        for key, expected in sorted(PUBLIC_EXPECTED.items()):
            if isinstance(expected, dict):
                check(f"public:summary:{key}", public.summary[key] == expected, json.dumps(public.summary[key], sort_keys=True))
            elif key in public.summary:
                check(f"public:summary:{key}", public.summary[key] == expected, str(public.summary[key]))
            else:
                check(f"public:structure:{key}", public.structure_summary[key] == expected, str(public.structure_summary[key]))
        check("public:digest-deterministic", public.digest() == bridge.analyze(public_image, public_contract, public_flat).digest(), "stable digest")

        public_record = {
            "schema": "openrecomp-phase9-pipeline-v1",
            "stage": STAGE,
            "fixture": fixture.PUBLIC_FIXTURE.label,
            "fixture_sha256": sha256(public_bytes),
            "summary": public.summary,
            "structure_summary": public.structure_summary,
            "digest": public.digest(),
        }
        write_json(evidence / "public_pipeline.json", public_record)

        # --- injected indirect call fails closed ---------------------------
        injected_words = list(fixture.build_words())
        bad_index = len(injected_words)
        injected_words += [
            builder.r_type("jalr", rs=8, rd=31),
            builder.nop(),
            builder.r_type("jr", rs=31),
            builder.nop(),
        ]
        injected_words[38] = builder.j_type("jal", fixture.PROGRAM_LOAD_ADDRESS + 4 * bad_index)
        injected_image = psx.ingest(builder.build_from_words(injected_words))
        injected_contract = memory_map.build_contract(injected_image)
        injected_flat = memory_map.flat_image(injected_image)
        injected = bridge.analyze(injected_image, injected_contract, injected_flat)
        check("injected:blocker-kind", (injected.first_blocker or {}).get("kind") == "indirect-call", str(injected.first_blocker))
        check("injected:unresolved", injected.summary["unresolved_site_counts"] == {"indirect-call": 1}, json.dumps(injected.summary["unresolved_site_counts"], sort_keys=True))
        check("injected:structure-unresolved", bool(injected.structure_summary and injected.structure_summary["unresolved_sites"]), "unresolved sites")
        if injected.structure_summary and injected.structure_summary["unresolved_sites"]:
            site = injected.structure_summary["unresolved_sites"][0]
            check("injected:classification-kind", site["kind"] == "INDIRECT_CALL" and site["status"].startswith("UNRESOLVED"), json.dumps(site, sort_keys=True))

        # --- private fixture: exact frontier, fail-closed structure --------
        fixture_path = pathlib.Path(options.private_fixture)
        private_record = {
            "schema": "openrecomp-phase9-private-pipeline-v1",
            "stage": STAGE,
            "label": PRIVATE_FIXTURE_LABEL,
            "present": fixture_path.is_file(),
            "is_pass_criterion": False,
        }
        if fixture_path.is_file():
            private_bytes = fixture_path.read_bytes()
            private_image = psx.ingest(private_bytes)
            private_contract = memory_map.build_contract(private_image)
            private_flat = memory_map.flat_image(private_image)
            private = bridge.analyze(private_image, private_contract, private_flat)
            for key in (
                "reachable_words",
                "reachable_supported_words",
                "reachable_unsupported_words",
                "reachable_invalid_words",
                "unresolved_site_counts",
                "exception_site_count",
            ):
                expected = PRIVATE_EXPECTED[key]
                check(f"private:summary:{key}", private.summary[key] == expected, json.dumps(private.summary[key], sort_keys=True))
            blocker = private.first_blocker or {}
            check("private:blocker-site", blocker.get("site_hex") == PRIVATE_EXPECTED["first_blocker_site"], str(blocker.get("site_hex")))
            check("private:blocker-kind", blocker.get("kind") == PRIVATE_EXPECTED["first_blocker_kind"], str(blocker.get("kind")))
            check("private:blocker-op", blocker.get("op") == PRIVATE_EXPECTED["first_blocker_op"], str(blocker.get("op")))
            check(
                "private:structure-error",
                (private.structure_error or {}).get("code") == PRIVATE_EXPECTED["structure_error_code"],
                str(private.structure_error),
            )
            check("private:no-structure-summary", private.structure_summary is None, "fail closed")
            check("private:reachable-histogram", private.summary["reachable_op_histogram"].get("jalr") == 22, str(private.summary["reachable_op_histogram"].get("jalr")))
            private_record["summary"] = private.summary
            private_record["structure_error"] = private.structure_error
            private_record["first_blocker"] = private.first_blocker
            private_record["digest"] = private.digest()
            private_text = json.dumps(private_record, sort_keys=True)
            assert_no_payload_leak("private:pipeline", private_text, private_image.payload)
        write_json(evidence / "private_pipeline.json", private_record)
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
        "stage_name": "Existing MIPS32 pipeline integration",
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
    write_json(evidence / "p9_03_tests.json", record)

    for item in results:
        print(f"{item['status']}: {item['check']}")
    print(f"OPENRECOMP_P9_03={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(results)}")
    print(f"{TERMINAL_MARKER}={NOT_PROVEN}")
    print(f"{GENERAL_MARKER}={NOT_PROVEN}")
    print(f"{PLAYABILITY_MARKER}={NOT_PROVEN}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
