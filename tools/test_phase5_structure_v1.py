#!/usr/bin/env python3
"""OpenRecomp Phase-5 neutral program-structure gate (P5-04).

Verifies the real public fixture through the shared architecture-neutral
ProgramModel / CFG / function discovery / call graph / translation-unit /
indirect-control-flow layers, with explicit reset, NMI, IRQ and documented
BRK-continuation roots, complete control-flow ownership, no fabricated
function boundaries and exactly one unresolved indirect site with an empty
target set.

On success it emits::

    OPENRECOMP_P5_04=PASS
    OPENRECOMP_PHASE5_NEUTRAL_STRUCTURE_V1=PASS tests=<count>
    OPENRECOMP_PHASE5_NES_PLATFORM_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE5_GENERAL_NES_COMPATIBILITY=NOT_PROVEN
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / ".openrecomp-phase5" / "src"), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import p5_fixture_build_v1 as fixture_build  # noqa: E402
import p5_ines_v1 as ingestion  # noqa: E402
import p5_structure_v1 as structure  # noqa: E402

STAGE = "P5-04"
STAGE_MARKER = "OPENRECOMP_P5_04"
FEATURE_MARKER = "OPENRECOMP_PHASE5_NEUTRAL_STRUCTURE_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE5_NES_PLATFORM_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE5_GENERAL_NES_COMPATIBILITY"

EXPECTED = {
    "instructions": 231,
    "blocks": 48,
    "functions": 11,
    "translation_units": 11,
    "call_edges": 7,
    "cfg_fingerprint": "d6dfe7a8aa82d146645999878361b74a606722f560b0228d19364757e9478c59",
    "discovery_fingerprint": "2839d54fa17e5ce2e77aef2bd8e79cd2571fdf6375522b75b643abc81f6a853c",
    "call_graph_fingerprint": "f0a4381ee30dbaa722bb309d51e0461edccf5814611d8c15031461a134e2d6d0",
    "units_fingerprint": "5523eae9fe4eee627c9ffdae5e89362d0b7e18fce089304c218c90fcaf6ebdb9",
    "classification_fingerprint": "6bc9b98fa42b683e61bb558e059bf9773c1a64061f47289fca7de14d2ebc5097",
    "region_sha256": "c8fd7527b34d84812a65a8f2a03d93de7f2b7da5256400c3f29c6860f58d33af",
}
ROOTS = {
    "reset": 0xC000,
    "nmi": 0xC196,
    "irq": 0xC1F7,
    "brk_continuation": 0xC0A8,
}
CALL_SITES = (
    (49193, 49408),
    (49196, 49422),
    (49199, 49446),
    (49202, 49470),
    (49297, 49552),
    (49357, 49539),
    (49573, 49521),
)
INDIRECT_SITE = 49405
TRAP_SITE = 0xC0A6
EXTRA_INSTRUCTIONS = [49319]

REGRESSIONS = (
    ("tools/test_nes6502_program_bridge_v1.py", []),
    ("tools/test_indirect_control_flow_v1.py", []),
)

RESULTS: list[dict[str, str]] = []
FINDINGS: dict[str, Any] = {}
EVIDENCE_WRITES: dict[str, bytes] = {}


def check(label: str, condition: bool) -> None:
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL"})
        print(f"FAIL: {label}", flush=True)
        raise AssertionError(f"{label}: condition failed")
    RESULTS.append({"check": label, "status": "PASS"})
    print(f"PASS: {label}", flush=True)


def banner(name: str) -> None:
    print(f"\n--- {name} ---", flush=True)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def lf_normalize(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def canonical(document: Any) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_json(name: str, document: Any) -> None:
    EVIDENCE_WRITES[name] = canonical(document)


def run_regression(script: str, extra: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(ROOT / script), *extra],
        cwd=str(ROOT), capture_output=True)
    return {
        "script": script,
        "returncode": completed.returncode,
        "stdout_bytes": len(completed.stdout),
        "stdout_sha256_raw": sha256_bytes(completed.stdout),
        "stdout_sha256_lf": sha256_bytes(lf_normalize(completed.stdout)),
        "stderr_bytes": len(completed.stderr),
        "stderr_empty": len(completed.stderr) == 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="P5-04 neutral structure gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase5/evidence/P5-04")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}

    print("=== P5-04 Neutral Program Structure Gate ===", flush=True)
    failure: str | None = None
    try:
        banner("structure")
        rom, metadata = fixture_build.build()
        inventory = ingestion.ingest(rom, source_label="public_fixture").to_document()
        document_a = structure.build_structure(rom, metadata, inventory)
        document_b = structure.build_structure(rom, metadata, inventory)
        check("structure:deterministic", canonical(document_a) == canonical(document_b))
        check("structure:instructions",
              document_a["instructions"] == EXPECTED["instructions"])
        check("structure:blocks", document_a["blocks"] == EXPECTED["blocks"])
        check("structure:functions",
              len(document_a["function_entries"]) == EXPECTED["functions"])
        check("structure:translation-units",
              document_a["translation_units"] == EXPECTED["translation_units"])
        check("structure:call-edges",
              len(document_a["call_edges"]) == EXPECTED["call_edges"])
        check("structure:fingerprints",
              document_a["cfg_fingerprint"] == EXPECTED["cfg_fingerprint"]
              and document_a["discovery_fingerprint"] == EXPECTED["discovery_fingerprint"]
              and document_a["call_graph_fingerprint"] == EXPECTED["call_graph_fingerprint"]
              and document_a["units_fingerprint"] == EXPECTED["units_fingerprint"]
              and document_a["classification_fingerprint"]
              == EXPECTED["classification_fingerprint"])
        check("structure:region-sha256",
              document_a["region_sha256"] == EXPECTED["region_sha256"])

        banner("roots")
        for name, address in ROOTS.items():
            check(f"root:{name}:address",
                  document_a["roots"][name]["address"] == address)
            check(f"root:{name}:basis",
                  bool(document_a["roots"][name]["basis"]))
        check("roots:entry-set",
              sorted(document_a["entry_addresses"]) == sorted(ROOTS.values()))
        check("roots:function-entries",
              all(address in document_a["function_entries"]
                  for address in ROOTS.values()))

        banner("boundaries")
        check("boundaries:no-violations", document_a["boundary_violations"] == [])
        check("boundaries:call-sites",
              [(item["address"], item["target"])
               for item in document_a["call_sites"]] == list(CALL_SITES))
        check("boundaries:unowned-control-flow",
              document_a["unowned_control_flow"] == [])
        check("boundaries:trap-site", document_a["trap_sites"] == [TRAP_SITE])

        banner("indirect")
        indirect = document_a["indirect_classifications"]
        check("indirect:single-site", len(indirect) == 1)
        check("indirect:site",
              indirect[0]["address"] == INDIRECT_SITE
              and indirect[0]["kind"] == "INDIRECT_JUMP"
              and indirect[0]["status"] == "UNRESOLVED_INDIRECT_JUMP")
        check("indirect:no-fabricated-targets",
              indirect[0]["targets"] == [] and indirect[0]["target_functions"] == [])

        banner("reachable_relationship")
        check("reachable:neutral-superset",
              document_a["missing_instructions"] == [])
        check("reachable:extra-instructions",
              document_a["extra_instructions"] == EXTRA_INSTRUCTIONS)

        banner("regressions")
        regressions = []
        for script, extra in REGRESSIONS:
            record = run_regression(script, extra)
            check(f"regression:{script}:exit", record["returncode"] == 0)
            check(f"regression:{script}:stderr", record["stderr_empty"])
            regressions.append(record)
        FINDINGS["regressions"] = regressions

        banner("evidence")
        write_json("structure.json", document_a)
        write_json("boundaries.json", {
            "stage": STAGE,
            "roots": document_a["roots"],
            "function_entries": document_a["function_entries"],
            "call_sites": document_a["call_sites"],
            "trap_sites": document_a["trap_sites"],
            "indirect_classifications": document_a["indirect_classifications"],
            "boundary_violations": document_a["boundary_violations"],
            "extra_instructions": document_a["extra_instructions"],
            "missing_instructions": document_a["missing_instructions"],
        })
        write_json("regressions.json", {"stage": STAGE, "regressions": regressions})
        for name, data in EVIDENCE_WRITES.items():
            check(f"hygiene:no-public-rom-bytes:{name}", rom not in data)
        FINDINGS["evidence_files"] = sorted(EVIDENCE_WRITES)
    except Exception as exc:  # noqa: BLE001 - fail closed without traceback
        failure = f"{type(exc).__name__}: {exc}"

    passed = sum(1 for item in RESULTS if item["status"] == "PASS")
    failed = sum(1 for item in RESULTS if item["status"] == "FAIL") + (1 if failure else 0)
    status = "FAIL" if failure else "PASS"

    result = {
        "stage": STAGE,
        "stage_name": FEATURE_MARKER,
        "status": status,
        "tests": passed,
        "passed": passed,
        "failed": failed,
        "markers": {
            "stage": f"{STAGE_MARKER}={status}",
            "gate": f"{FEATURE_MARKER}={status} tests={passed}",
            "terminal": f"{TERMINAL_MARKER}=NOT_PROVEN",
            "compatibility": f"{COMPAT_MARKER}=NOT_PROVEN",
        },
        "checks": sorted(RESULTS, key=lambda item: item["check"]),
        "findings": FINDINGS,
        "failure": failure,
    }
    for name, data in EVIDENCE_WRITES.items():
        (EVIDENCE_DIR / name).write_bytes(data)
    (EVIDENCE_DIR / "p5_04_tests.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        newline="\n")

    print("\n=== RESULT ===")
    print(f"{STAGE_MARKER}={status}")
    print(f"{FEATURE_MARKER}={status} tests={passed}")
    print(f"{TERMINAL_MARKER}=NOT_PROVEN")
    print(f"{COMPAT_MARKER}=NOT_PROVEN")
    if failure:
        print(f"FAILURE={failure}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
