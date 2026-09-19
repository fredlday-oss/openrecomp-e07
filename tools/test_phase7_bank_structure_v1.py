#!/usr/bin/env python3
"""OpenRecomp Phase-7 bank-aware structure gate (P7-05).

Verifies bank-aware neutral ProgramModel / CFG / function / call-graph /
translation-unit integration on the original Apache-2.0 public bank-switching
fixture: per-physical-bank structures, real cross-bank call entries in both
directions, no fabricated cross-bank edges, no merged bank identities,
documented native/reference execution and deterministic fail-closed behavior.

On success it emits::

    OPENRECOMP_P7_05=PASS
    OPENRECOMP_PHASE7_BANK_STRUCTURE_V1=PASS tests=<count>
    OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN
    OPENRECOMP_PHASE7_TMMT_PLAYABILITY=NOT_PROVEN

Usage:

    python tools/test_phase7_bank_structure_v1.py \
        --evidence-dir .openrecomp-phase7/evidence/P7-05
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTROL7 = ROOT / ".openrecomp-phase7"
for entry in (str(ROOT), str(ROOT / "tools"),
              str(ROOT / ".openrecomp-phase5" / "src"),
              str(ROOT / ".openrecomp-phase6" / "src"),
              str(CONTROL7 / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import adapters.nes6502 as nes  # noqa: E402
import p6_private_fixture_v1 as private_fixture  # noqa: E402
import p7_bank_reachability_v1 as model  # noqa: E402
import p7_bank_structure_v1 as structure  # noqa: E402
import p7_bank_switching_fixture_v1 as fixture  # noqa: E402
import p7_dispatch_reference_v1 as dispatch_reference  # noqa: E402

STAGE = "P7-05"
STAGE_MARKER = "OPENRECOMP_P7_05"
FEATURE_MARKER = "OPENRECOMP_PHASE7_BANK_STRUCTURE_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE7_TMMT_PLAYABILITY"

P7_04_RECORD_REL = ".openrecomp-phase7/evidence/P7-04/p7_04_tests.json"
P7_04_GATE = "tools/test_phase7_bank_reachability_v1.py"
P7_03_RECORD_REL = ".openrecomp-phase7/evidence/P7-03/p7_03_tests.json"

EXPECTED = {
    "cross_bank_calls": (
        (3, 1, 0x8000, "call"),
        (1, 3, 0xC100, "call"),
    ),
    "bank_proven_instructions": {1: 4, 3: 22},
    "markers": {"marker": 0x77, "selector": 0x77, "resume_out": 0x42},
}

REGRESSIONS = ("tools/test_nes_rom_v1.py",)

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


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical(document: Any) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True)
            + "\n").encode("utf-8")


def canonical_text(document: Any) -> str:
    return json.dumps(document, sort_keys=True, separators=(",", ":"))


def write_json(name: str, document: Any) -> None:
    EVIDENCE_WRITES[name] = canonical(document)


def read_json(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def run_regression(script: str, extra: list[str] | None = None) -> dict[str, Any]:
    completed = subprocess.run([sys.executable, script, *(extra or [])],
                               cwd=str(ROOT), capture_output=True)
    stdout = completed.stdout
    stderr = completed.stderr
    markers = [line for line in stdout.decode("utf-8", errors="replace").splitlines()
               if line.startswith("OPENRECOMP_")]
    return {
        "script": script,
        "command": ["python", script, *(extra or [])],
        "returncode": completed.returncode,
        "stdout_bytes": len(stdout),
        "stdout_sha256_raw": sha256_bytes(stdout),
        "stdout_sha256_lf": sha256_bytes(stdout.replace(b"\r\n", b"\n")),
        "stderr_bytes": len(stderr),
        "stderr_empty": not stderr,
        "markers": markers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P7-05 bank-aware structure gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase7/evidence/P7-05")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES, SCRATCH
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    SCRATCH = CONTROL7 / "scratch" / "P7-05"
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}

    print("=== P7-05 Bank-Aware Structure Gate ===", flush=True)
    failure: str | None = None
    try:
        banner("source_integrity")
        manifest = CONTROL7 / "SOURCE_SHA256SUMS.txt"
        entries = []
        for line in manifest.read_text(encoding="utf-8").strip().splitlines():
            digest, rel = line.split(" *", 1)
            entries.append((digest, rel))
        bad = [rel for digest, rel in entries
               if not (ROOT / rel).is_file() or sha256_file(ROOT / rel) != digest]
        check("source:manifest-verified", bool(entries) and not bad)

        banner("anchors")
        check("anchor:p7-03-record-pass",
              read_json(ROOT / P7_03_RECORD_REL)["status"] == "PASS")
        check("anchor:p7-04-record-pass",
              read_json(ROOT / P7_04_RECORD_REL)["status"] == "PASS")
        check("anchor:decoder-unchanged", len(nes.OPCODES) == 151)

        banner("control_plane")
        state = (CONTROL7 / "STATE.md").read_text(encoding="utf-8")
        queue = (CONTROL7 / "STAGE_QUEUE.md").read_text(encoding="utf-8")
        check("control-plane:stage-row", "| P7-05 |" in queue)
        check("control-plane:terminal-reserved",
              f"{TERMINAL_MARKER}=NOT_PROVEN" in queue
              and f"{TERMINAL_MARKER}=NOT_PROVEN" in state)
        check("control-plane:compat-reserved",
              f"{COMPAT_MARKER}=NOT_PROVEN" in queue
              and f"{COMPAT_MARKER}=NOT_PROVEN" in state)
        check("control-plane:playability-reserved",
              f"{PLAYABILITY_MARKER}=NOT_PROVEN" in queue
              and f"{PLAYABILITY_MARKER}=NOT_PROVEN" in state)

        banner("fixture_build")
        rom_a, metadata_a = fixture.build()
        rom_b, metadata_b = fixture.build()
        check("fixture:deterministic",
              rom_a == rom_b
              and canonical_text(metadata_a) == canonical_text(metadata_b))
        check("fixture:license-and-origin",
              metadata_a["license"] == "Apache-2.0"
              and metadata_a["origin"] == "original")
        source_text = fixture.ASM_PATH.read_text(encoding="utf-8")
        check("fixture:source-provenance",
              "Apache-2.0" in source_text
              and "original work" in source_text
              and "no third-party or console-derived program data" in source_text)
        check("fixture:assembled-cross-checked",
              metadata_a["instruction_count"] > 0
              and metadata_a["instructions_cross_checked"]
              == metadata_a["instruction_count"])
        inventory = fixture.inventory(rom_a)
        check("fixture:inventory",
              inventory["phase6"]["status"] == "SUPPORTED_MMC1"
              and inventory["prg_bytes"] == 0x10000
              and inventory["chr_bytes"] == 0x2000
              and inventory["vectors"]["reset"] == 0xC000)
        prg = rom_a[16:16 + inventory["prg_bytes"]]
        roots = [inventory["vectors"][name]
                 for name in ("reset", "nmi", "irq")]
        FINDINGS["fixture"] = {
            "rom_sha256": metadata_a["rom_sha256"],
            "rom_size": metadata_a["rom_size"],
            "prg_sha256": metadata_a["prg_sha256"],
            "exit_site": metadata_a["exit_site"],
        }

        banner("bank_reachability")
        reachability = model.analyze(prg, metadata_a["prg_banks"], roots)
        check("reachability:status",
              reachability["status"] == "OK"
              and reachability["proven_instructions"] == 26
              and reachability["unresolved_instructions"] == 0)
        banks_found = {entry["bank"]: entry for entry
                       in reachability["code_by_bank"]}
        check("reachability:banks",
              sorted(banks_found) == [1, 3]
              and all(entry["proven_instructions"]
                      == EXPECTED["bank_proven_instructions"][bank]
                      for bank, entry in banks_found.items()))
        cross_edges = [edge for edge in reachability["edges"]
                       if edge["src_bank"] != edge["dst_bank"]]
        check("reachability:cross-bank-calls",
              sorted((edge["src_bank"], edge["dst_bank"],
                      edge["dst_address"], edge["kind"])
                     for edge in cross_edges)
              == sorted(EXPECTED["cross_bank_calls"]))
        check("reachability:no-merge",
              reachability["multi_bank_cpu_addresses"] == {})

        banner("bank_structure")
        document = structure.build(prg, metadata_a["prg_banks"],
                                   reachability, roots=roots)
        check("structure:two-banks",
              document["bank_count"] == 2
              and sorted(entry["bank"] for entry in document["banks"])
              == [1, 3]
              and document["cross_bank_edge_count"] == 2)
        by_bank = {entry["bank"]: entry for entry in document["banks"]}
        check("structure:bank-instruction-counts",
              all(by_bank[bank]["proven_instructions"]
                  == EXPECTED["bank_proven_instructions"][bank]
                  for bank in (1, 3)))
        check("structure:cross-entries",
              by_bank[1]["cross_bank_entries"] == [0x8000]
              and by_bank[3]["cross_bank_entries"] == [0xC100]
              and 0x8000 in by_bank[1]["function_entries"]
              and 0xC100 in by_bank[3]["function_entries"])
        check("structure:external-targets",
              [(entry["op"], entry["target"], entry["dst_bank"])
               for entry in by_bank[1]["external_targets"]]
              == [("jsr", 0xC100, 3)]
              and [(entry["op"], entry["target"], entry["dst_bank"])
                   for entry in by_bank[3]["external_targets"]]
              == [("jsr", 0x8000, 1)])
        check("structure:neutral-fingerprints",
              all(entry["cfg_fingerprint"]
                  and entry["discovery_fingerprint"]
                  and entry["call_graph_fingerprint"]
                  and entry["units_fingerprint"]
                  and entry["classification_fingerprint"]
                  for entry in document["banks"])
              and by_bank[1]["blocks"] >= 1
              and by_bank[3]["blocks"] >= 1
              and by_bank[3]["functions"] >= 2
              and by_bank[3]["translation_units"] >= 2)
        check("structure:unresolved-indirect-sites",
              len(by_bank[3]["indirect_sites"]) == 1
              and by_bank[3]["indirect_sites"][0]["address"]
              == metadata_a["exit_site"]
              and by_bank[3]["indirect_sites"][0]["targets"] == [])
        check("structure:no-unresolved-identities",
              document["rejected_unresolved_identities"] == [])
        FINDINGS["structure"] = {
            "banks": [
                {"bank": entry["bank"],
                 "instructions": entry["proven_instructions"],
                 "blocks": entry["blocks"],
                 "functions": entry["functions"],
                 "units": entry["translation_units"],
                 "cross_bank_entries": entry["cross_bank_entries"]}
                for entry in document["banks"]],
            "cross_bank_edges": document["cross_bank_edges"],
        }

        banner("reference_execution")
        run = dispatch_reference.run(rom_a, inventory,
                                     exit_site=metadata_a["exit_site"])
        check("reference:exit", run["exit_reached"] is True
              and run["pc"] == metadata_a["exit_site"])
        check("reference:markers",
              all(run["markers"][name] == value
                  for name, value in EXPECTED["markers"].items()))
        check("reference:cross-bank-code-executed",
              0x8000 in run["executed_addresses"]
              and 0xC100 in run["executed_addresses"])
        FINDINGS["reference"] = {
            "steps": run["steps"],
            "markers": run["markers"],
            "executed_count": run["executed_count"],
        }

        banner("no_fabrication")
        mutated = copy.deepcopy(reachability)
        for edge in mutated["edges"]:
            if edge["src_bank"] == 3 and edge["dst_bank"] == 1 \
                    and edge["kind"] == "call":
                edge["dst_bank"] = 2
        try:
            structure.build(prg, metadata_a["prg_banks"], mutated, roots=roots)
        except structure.P7BankStructureError:
            check("negative:mutated-cross-bank-edge-rejected", True)
        else:
            raise AssertionError("negative:mutated-cross-bank-edge-rejected")
        mutated = copy.deepcopy(reachability)
        mutated["edges"] = [edge for edge in mutated["edges"]
                            if not (edge["src_bank"] == 3
                                    and edge["dst_bank"] == 1)]
        try:
            structure.build(prg, metadata_a["prg_banks"], mutated, roots=roots)
        except structure.P7BankStructureError:
            check("negative:missing-cross-bank-edge-rejected", True)
        else:
            raise AssertionError("negative:missing-cross-bank-edge-rejected")
        blocked = copy.deepcopy(reachability)
        blocked["status"] = "BLOCKED_BUDGET"
        try:
            structure.build(prg, metadata_a["prg_banks"], blocked, roots=roots)
        except structure.P7BankStructureError:
            check("negative:blocked-reachability-rejected", True)
        else:
            raise AssertionError("negative:blocked-reachability-rejected")
        try:
            model.analyze(prg[:-1], metadata_a["prg_banks"], roots)
        except model.BankReachabilityError:
            check("negative:truncated-prg-rejected", True)
        else:
            raise AssertionError("negative:truncated-prg-rejected")

        banner("regressions")
        regressions = []
        for script in REGRESSIONS:
            record = run_regression(script)
            check(f"regression:{script}:exit", record["returncode"] == 0)
            check(f"regression:{script}:stderr", record["stderr_empty"])
            regressions.append(record)
        p7_04_regression = run_regression(
            P7_04_GATE, ["--evidence-dir",
                         ".openrecomp-phase7/scratch/P7-05/regression_p7_04"])
        check("regression:p7-04:exit", p7_04_regression["returncode"] == 0)
        check("regression:p7-04:stderr", p7_04_regression["stderr_empty"])
        check("regression:p7-04:marker",
              any(marker == "OPENRECOMP_P7_04=PASS"
                  for marker in p7_04_regression["markers"]))
        regressions.append(p7_04_regression)
        FINDINGS["regressions"] = regressions

        banner("evidence")
        write_json("bank_structure.json", {
            "stage": STAGE,
            "fixture": {
                "name": metadata_a["fixture"],
                "license": metadata_a["license"],
                "source": metadata_a["source"],
                "source_sha256": metadata_a["source_sha256"],
                "rom_sha256": metadata_a["rom_sha256"],
                "rom_size": metadata_a["rom_size"],
                "prg_sha256": metadata_a["prg_sha256"],
                "chr_sha256": metadata_a["chr_sha256"],
                "prg_banks": metadata_a["prg_banks"],
                "chr_banks": metadata_a["chr_banks"],
                "vectors": inventory["vectors"],
                "exit_site": metadata_a["exit_site"],
            },
            "reachability": {
                "status": reachability["status"],
                "proven_instructions": reachability["proven_instructions"],
                "unresolved_instructions":
                    reachability["unresolved_instructions"],
                "code_by_bank": reachability["code_by_bank"],
                "cross_bank_edges": cross_edges,
                "multi_bank_cpu_addresses":
                    reachability["multi_bank_cpu_addresses"],
            },
            "structure": document,
            "reference": FINDINGS["reference"],
            "non_fabrication_claim":
                "cross-bank edges are exactly the proven bank-qualified "
                "reachability edges; mutated or missing edges fail closed",
            "public_claim": metadata_a["public_claim"],
        })
        private_bytes = private_fixture.PRIVATE_ROM.read_bytes()
        for name, data in EVIDENCE_WRITES.items():
            check(f"hygiene:no-private-rom-bytes:{name}", private_bytes not in data)
        check("hygiene:no-rom-extension-in-scratch",
              not any(path.suffix.lower() in (".nes", ".fds", ".unf", ".unif")
                      for path in SCRATCH.rglob("*") if path.is_file()))
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
            "playability": f"{PLAYABILITY_MARKER}=NOT_PROVEN",
        },
        "checks": sorted(RESULTS, key=lambda item: item["check"]),
        "findings": FINDINGS,
        "failure": failure,
    }
    for name, data in EVIDENCE_WRITES.items():
        (EVIDENCE_DIR / name).write_bytes(data)
    (EVIDENCE_DIR / "p7_05_tests.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        newline="\n")

    print("\n=== RESULT ===")
    print(f"{STAGE_MARKER}={status}")
    print(f"{FEATURE_MARKER}={status} tests={passed}")
    print(f"{TERMINAL_MARKER}=NOT_PROVEN")
    print(f"{COMPAT_MARKER}=NOT_PROVEN")
    print(f"{PLAYABILITY_MARKER}=NOT_PROVEN")
    if failure:
        print(f"FAILURE={failure}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
