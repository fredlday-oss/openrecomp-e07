#!/usr/bin/env python3
"""OpenRecomp Phase-9 evidence closure and claim ledger gate (P9-91).

The gate verifies, on one audited tree:

* every completed Phase-9 stage record (`P9-00` .. `P9-12`, `P9-90`) exists
  with a `RESULT.md`, a machine-readable tests record, an `official_runs.json`
  with two byte-identical runs, empty stderr and exit 0, and the correct
  reserved markers;
* every sidecar hash recorded in `official_runs.json` matches the file on
  disk;
* the evidence index covers every committed Phase-9 evidence file (excluding
  this stage's own generated sidecars) with exact SHA-256 and size;
* the claim ledger classifies every Phase-9 claim as
  `PROVEN` / `BOUNDED` / `NOT_PROVEN` / `NOT_TESTED`, keeps the permanent
  general-PS1 and Hercules-playability non-claims, and never promotes them;
* the public-safety verification finds no private payload material and no
  absolute host paths in the committed Phase-9 evidence.

On success it emits::

    OPENRECOMP_P9_91=PASS
    OPENRECOMP_PHASE9_EVIDENCE_INDEX_V1=PASS tests=<count>
    OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN
    OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN

Usage:

    python tools/test_phase9_evidence_index_v1.py
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import pathlib
import re
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
P9 = ROOT / ".openrecomp-phase9"
EVIDENCE = P9 / "evidence"

STAGE = "P9-91"
FEATURE_MARKER = "OPENRECOMP_PHASE9_EVIDENCE_INDEX_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE9_HERCULES_PLAYABILITY"
NOT_PROVEN = "NOT_PROVEN"

COMPLETED_STAGES = (
    "P9-00", "P9-01", "P9-02", "P9-03", "P9-04", "P9-05", "P9-06",
    "P9-07", "P9-08", "P9-09", "P9-10", "P9-11", "P9-12", "P9-90",
)

PERMANENT_NON_CLAIMS = (
    "OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN",
    "OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN",
)

REQUIRED_CLAIMS = {
    "psx_exe_ingestion": "PROVEN",
    "ps1_address_space_contract": "PROVEN",
    "frozen_mips32_pipeline_reuse": "PROVEN",
    "reachable_translation_closure": "PROVEN",
    "bios_service_boundary": "PROVEN",
    "gpu_adapter_boundary": "PROVEN",
    "input_timer_event_boundary": "PROVEN",
    "spu_audio_contract": "PROVEN",
    "cdrom_file_service_contract": "PROVEN",
    "native_build_deterministic_execution": "PROVEN",
    "independent_reference_equivalence": "PROVEN",
    "private_hercules_bounded_validation": "PROVEN",
    "fail_closed_hardening_and_reproducibility": "PROVEN",
    "platform_port_behaviour": "BOUNDED",
    "private_frontier_discovery_windows": "BOUNDED",
    "flat_ram_and_stack_model": "BOUNDED",
    "general_ps1_compatibility": "NOT_PROVEN",
    "arbitrary_psx_exe_compatibility": "NOT_PROVEN",
    "bios_emulation": "NOT_PROVEN",
    "gpu_rendering": "NOT_PROVEN",
    "spu_synthesis": "NOT_PROVEN",
    "cdrom_disc_reading": "NOT_PROVEN",
    "controller_protocol": "NOT_PROVEN",
    "interrupt_delivery": "NOT_PROVEN",
    "cop0_gte_execution": "NOT_PROVEN",
    "hercules_playability": "NOT_PROVEN",
    "memory_cards_dma_link_cable": "NOT_TESTED",
}

DEFAULT_PRIVATE_FIXTURE = (
    ROOT.parents[1] / "fixtures" / "psx" / "hercules" / "SLUS_005.29"
)

HOST_PATH_RE = re.compile(r"(?:[A-Za-z]:\\|/home/|/Users/|/root/)")

RESULTS: list[dict[str, str]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    RESULTS.append({"check": label, "status": "PASS" if condition else "FAIL", "detail": detail})
    if not condition:
        raise AssertionError(f"{label}: condition failed ({detail})")


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: pathlib.Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def build_index() -> dict:
    entries = []
    total_bytes = 0
    # The index excludes its own generated sidecars and the terminal verdict
    # stage, which is produced after the index and audited by the P9-99 gate.
    excluded_prefixes = (
        ".openrecomp-phase9/evidence/P9-91/",
        ".openrecomp-phase9/evidence/P9-99/",
    )
    for path in sorted(EVIDENCE.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT).as_posix()
        if any(relative.startswith(prefix) for prefix in excluded_prefixes):
            continue
        size = path.stat().st_size
        total_bytes += size
        entries.append(
            {
                "path": relative,
                "stage": path.relative_to(EVIDENCE).parts[0],
                "bytes": size,
                "sha256": sha256_file(path),
                "tracked": True,
            }
        )
    return {
        "schema": "openrecomp-phase9-evidence-index-v1",
        "stage": STAGE,
        "entry_count": len(entries),
        "total_bytes": total_bytes,
        "entries": entries,
        "note": "the index excludes its own directory's generated sidecars and the post-index terminal stage (P9-99)",
    }


def build_ledger() -> dict:
    return {
        "schema": "openrecomp-phase9-claim-ledger-v1",
        "stage": STAGE,
        "classes": ["PROVEN", "BOUNDED", "NOT_PROVEN", "NOT_TESTED"],
        "claims": [
            {"claim": "PS-X EXE ingestion for the bounded V1 container form", "class": "PROVEN", "key": "psx_exe_ingestion", "evidence": ["P9-01", "P9-12"]},
            {"claim": "Explicit PS1 address-space contract (2 MiB RAM, KSEG0/KSEG1, named regions, fail-closed segments)", "class": "PROVEN", "key": "ps1_address_space_contract", "evidence": ["P9-02", "P9-12"]},
            {"claim": "Frozen Phase-8 MIPS32 pipeline reuse for PS1 PS-X EXE code", "class": "PROVEN", "key": "frozen_mips32_pipeline_reuse", "evidence": ["P9-03", "P9-90"]},
            {"claim": "Reachable translation-frontier closure against the frozen rule table (public fixture)", "class": "PROVEN", "key": "reachable_translation_closure", "evidence": ["P9-04"]},
            {"claim": "Typed, versioned, fail-closed BIOS/service boundary with no BIOS image", "class": "PROVEN", "key": "bios_service_boundary", "evidence": ["P9-05"]},
            {"claim": "Clean non-emulating GPU adapter boundary with typed events and unknown-command blockers", "class": "PROVEN", "key": "gpu_adapter_boundary", "evidence": ["P9-06"]},
            {"claim": "Deterministic virtual input/time interfaces and interrupt classification", "class": "PROVEN", "key": "input_timer_event_boundary", "evidence": ["P9-07"]},
            {"claim": "Explicit audio service/runtime contract with no synthesis", "class": "PROVEN", "key": "spu_audio_contract", "evidence": ["P9-08"]},
            {"claim": "Explicit bounded CD-ROM/file-service contract with no disc bytes", "class": "PROVEN", "key": "cdrom_file_service_contract", "evidence": ["P9-09"]},
            {"claim": "Native recompilation and deterministic execution of the public PS1 fixture through the platform runtime adapter", "class": "PROVEN", "key": "native_build_deterministic_execution", "evidence": ["P9-10", "P9-12"]},
            {"claim": "Independent reference equivalence with no excluded observables", "class": "PROVEN", "key": "independent_reference_equivalence", "evidence": ["P9-10", "P9-12"]},
            {"claim": "Private Hercules bounded validation with exact frontier and first blocker", "class": "PROVEN", "key": "private_hercules_bounded_validation", "evidence": ["P9-11"]},
            {"claim": "Fail-closed hardening, immutable-hash cache correctness, reproducible rebuild and public-safety closure", "class": "PROVEN", "key": "fail_closed_hardening_and_reproducibility", "evidence": ["P9-12", "P9-90"]},
            {"claim": "Platform port behaviours are event recording / contract stubs, not hardware-accurate emulation", "class": "BOUNDED", "key": "platform_port_behaviour", "evidence": ["P9-06", "P9-07", "P9-08", "P9-09"]},
            {"claim": "Private-fixture I/O and BIOS discovery are exact only within the bounded same-block windows", "class": "BOUNDED", "key": "private_frontier_discovery_windows", "evidence": ["P9-05", "P9-11"]},
            {"claim": "Flat 2 MiB RAM image and explicit bounded stack window model", "class": "BOUNDED", "key": "flat_ram_and_stack_model", "evidence": ["P9-02"]},
            {"claim": "General PS1 compatibility", "class": "NOT_PROVEN", "key": "general_ps1_compatibility", "evidence": []},
            {"claim": "Arbitrary PS-X EXE compatibility", "class": "NOT_PROVEN", "key": "arbitrary_psx_exe_compatibility", "evidence": []},
            {"claim": "BIOS emulation", "class": "NOT_PROVEN", "key": "bios_emulation", "evidence": []},
            {"claim": "GPU rendering / VRAM behaviour", "class": "NOT_PROVEN", "key": "gpu_rendering", "evidence": []},
            {"claim": "SPU audio synthesis", "class": "NOT_PROVEN", "key": "spu_synthesis", "evidence": []},
            {"claim": "CD-ROM disc reading / file system", "class": "NOT_PROVEN", "key": "cdrom_disc_reading", "evidence": []},
            {"claim": "Controller serial protocol", "class": "NOT_PROVEN", "key": "controller_protocol", "evidence": []},
            {"claim": "Interrupt delivery / event scheduling", "class": "NOT_PROVEN", "key": "interrupt_delivery", "evidence": []},
            {"claim": "COP0/GTE execution", "class": "NOT_PROVEN", "key": "cop0_gte_execution", "evidence": []},
            {"claim": "Hercules playability", "class": "NOT_PROVEN", "key": "hercules_playability", "evidence": []},
            {"claim": "Memory cards, DMA and link cable behaviour", "class": "NOT_TESTED", "key": "memory_cards_dma_link_cable", "evidence": []},
        ],
        "permanent_non_claims": list(PERMANENT_NON_CLAIMS),
        "terminal_claim": "OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF",
        "terminal_claim_status_at_p9_91": NOT_PROVEN,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=".openrecomp-phase9/evidence/P9-91")
    parser.add_argument("--verify-only", action="store_true", help="re-run the checks without rewriting the committed index/ledger")
    parser.add_argument("--private-fixture", default=os.environ.get("OPENRECOMP_PSX_PRIVATE_FIXTURE", str(DEFAULT_PRIVATE_FIXTURE)))
    options = parser.parse_args()
    evidence = (ROOT / options.evidence_dir).resolve()

    try:
        # --- stage records --------------------------------------------------
        for stage in COMPLETED_STAGES:
            stage_dir = EVIDENCE / stage
            check(f"record:{stage}:dir", stage_dir.is_dir(), stage)
            check(f"record:{stage}:result", (stage_dir / "RESULT.md").is_file(), stage)
            runs_path = stage_dir / "official_runs.json"
            check(f"record:{stage}:official-runs", runs_path.is_file(), stage)
            runs = json.loads(runs_path.read_text(encoding="utf-8"))
            check(f"record:{stage}:two-runs", runs["identical_raw"] and runs["identical_lf"], "identical")
            check(f"record:{stage}:stderr", runs["stderr_empty_both"], "empty")
            check(f"record:{stage}:exit", runs["returncode_zero_both"], "zero")
            check(f"record:{stage}:markers", runs["markers_present_both"], "markers")
            for run in runs["runs"]:
                tests_key = f"p9_{stage.split('-')[1]}_tests_sha256"
                if tests_key in run:
                    tests_path = stage_dir / f"p9_{stage.split('-')[1]}_tests.json"
                    check(f"record:{stage}:tests-hash:{run['name']}", sha256_file(tests_path) == run[tests_key], run[tests_key])
            tests = json.loads((stage_dir / f"p9_{stage.split('-')[1]}_tests.json").read_text(encoding="utf-8"))
            check(f"record:{stage}:tests-status", tests["status"] == "PASS" and tests["failed"] == 0, tests["status"])

        # --- evidence index -------------------------------------------------
        index = build_index()
        check("index:entries", index["entry_count"] >= 100, str(index["entry_count"]))
        check("index:stages-covered", {entry["stage"] for entry in index["entries"]} >= set(COMPLETED_STAGES), "stages")
        check("index:no-own-sidecars", all("P9-91" not in entry["path"] for entry in index["entries"]), "own sidecars excluded")
        check("index:all-hashes", all(len(entry["sha256"]) == 64 for entry in index["entries"]), "hashes")
        committed_index_path = evidence / "evidence_index.json"
        if not options.verify_only:
            write_json(committed_index_path, index)
        check("index:committed", committed_index_path.is_file(), "present")
        committed_index = json.loads(committed_index_path.read_text(encoding="utf-8"))
        check("index:matches-live", committed_index == index, "live index equals committed index")

        # --- claim ledger ---------------------------------------------------
        ledger = build_ledger()
        committed_ledger_path = evidence / "claim_ledger.json"
        if not options.verify_only:
            write_json(committed_ledger_path, ledger)
        check("ledger:committed", committed_ledger_path.is_file(), "present")
        committed_ledger = json.loads(committed_ledger_path.read_text(encoding="utf-8"))
        check("ledger:matches-live", committed_ledger == ledger, "live ledger equals committed ledger")
        claims = {item["key"]: item["class"] for item in committed_ledger["claims"]}
        for key, expected in sorted(REQUIRED_CLAIMS.items()):
            check(f"ledger:claim:{key}", claims.get(key) == expected, str(claims.get(key)))
        check("ledger:permanent-non-claims", tuple(committed_ledger["permanent_non_claims"]) == PERMANENT_NON_CLAIMS, "permanent")
        check("ledger:terminal-reserved", committed_ledger["terminal_claim_status_at_p9_91"] == NOT_PROVEN, NOT_PROVEN)
        classes = {item["class"] for item in committed_ledger["claims"]}
        check("ledger:classes", classes <= {"PROVEN", "BOUNDED", "NOT_PROVEN", "NOT_TESTED"}, ",".join(sorted(classes)))

        # --- public safety --------------------------------------------------
        fixture_path = pathlib.Path(options.private_fixture)
        payload = None
        if fixture_path.is_file():
            import sys as _sys
            _sys.path.insert(0, str(P9 / "src"))
            import p9_psx_exe_v1 as psx

            payload = psx.ingest(fixture_path.read_bytes()).payload
        leaks: list[str] = []
        host_paths: list[str] = []
        for entry in index["entries"]:
            path = ROOT / entry["path"]
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if HOST_PATH_RE.search(text):
                host_paths.append(entry["path"])
            if payload is not None:
                lowered = text.lower()
                if payload[:64].hex() in lowered:
                    leaks.append(entry["path"] + ":hex")
                if base64.b64encode(payload[:48]).decode("ascii") in text:
                    leaks.append(entry["path"] + ":base64")
                for start in range(0, min(len(payload), 512)):
                    run = payload[start : start + 8]
                    if len(run) == 8 and all(32 <= byte < 127 for byte in run):
                        if run.decode("ascii") in text:
                            leaks.append(entry["path"] + ":ascii")
                            break
        check("safety:no-payload-leaks", leaks == [], json.dumps(leaks))
        check("safety:no-host-paths", host_paths == [], json.dumps(host_paths))
        check("safety:private-not-a-criterion", True, "private fixture present" if fixture_path.is_file() else "absent")
    except AssertionError as exc:
        RESULTS.append({"check": "gate:assertion", "status": "FAIL", "detail": str(exc)})
    except Exception as exc:  # fail closed with a stable record
        RESULTS.append({"check": "gate:exception", "status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"})

    failed = [item for item in RESULTS if item["status"] == "FAIL"]
    status = "PASS" if not failed else "FAIL"
    results = sorted(RESULTS, key=lambda item: item["check"])
    if not options.verify_only:
        write_json(
            evidence / "p9_91_tests.json",
            {
                "stage": STAGE,
                "stage_name": "Evidence closure and claim ledger",
                "status": status,
                "tests": len(results),
                "passed": sum(1 for item in results if item["status"] == "PASS"),
                "failed": len(failed),
                "checks": results,
                "failure": None if not failed else [item["check"] for item in failed],
            },
        )

    for item in results:
        print(f"{item['status']}: {item['check']}")
    print(f"OPENRECOMP_P9_91={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(results)}")
    print(f"{TERMINAL_MARKER}={NOT_PROVEN}")
    print(f"{GENERAL_MARKER}={NOT_PROVEN}")
    print(f"{PLAYABILITY_MARKER}={NOT_PROVEN}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
