#!/usr/bin/env python3
"""OpenRecomp Phase-7 public indirect-flow fixture gate (P7-07).

Verifies the original Apache-2.0 public indirect-control-flow fixture: exact
single-target dispatch, a masked four-entry finite target set and an
unresolved fail-closed dispatch site, all resolved under proven bank-1
provenance, with reference execution for all three runtime selectors and
model-vs-runtime differential checks.

On success it emits::

    OPENRECOMP_P7_07=PASS
    OPENRECOMP_PHASE7_INDIRECT_FIXTURE_V1=PASS tests=<count>
    OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN
    OPENRECOMP_PHASE7_TMMT_PLAYABILITY=NOT_PROVEN

Usage:

    python tools/test_phase7_indirect_fixture_v1.py \
        --evidence-dir .openrecomp-phase7/evidence/P7-07
"""
from __future__ import annotations

import argparse
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
import p7_bank_reachability_v1 as bank_model  # noqa: E402
import p7_indirect_evidence_v1 as evidence  # noqa: E402
import p7_indirect_flow_fixture_v1 as fixture  # noqa: E402
import p7_dispatch_reference_v1 as dispatch_reference  # noqa: E402

STAGE = "P7-07"
STAGE_MARKER = "OPENRECOMP_P7_07"
FEATURE_MARKER = "OPENRECOMP_PHASE7_INDIRECT_FIXTURE_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE7_TMMT_PLAYABILITY"

P7_06_RECORD_REL = ".openrecomp-phase7/evidence/P7-06/p7_06_tests.json"
P7_06_GATE = "tools/test_phase7_indirect_evidence_v1.py"

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
        description="P7-07 public indirect-flow fixture gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase7/evidence/P7-07")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES, SCRATCH
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    SCRATCH = CONTROL7 / "scratch" / "P7-07"
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}

    print("=== P7-07 Public Indirect-Flow Fixture Gate ===", flush=True)
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
        check("anchor:p7-06-record-pass",
              read_json(ROOT / P7_06_RECORD_REL)["status"] == "PASS")
        check("anchor:decoder-unchanged", len(nes.OPCODES) == 151)

        banner("control_plane")
        state = (CONTROL7 / "STATE.md").read_text(encoding="utf-8")
        queue = (CONTROL7 / "STAGE_QUEUE.md").read_text(encoding="utf-8")
        check("control-plane:stage-row", "| P7-07 |" in queue)
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
        for path in (fixture.FIXED_ASM, fixture.BANK_ASM):
            text = path.read_text(encoding="utf-8").lower()
            check(f"fixture:source-provenance:{path.name}",
                  "apache-2.0" in text and "original work" in text
                  and "no third-party or console-derived program data" in text)
        check("fixture:cross-checked",
              metadata_a["instruction_count"] > 0
              and metadata_a["instructions_cross_checked"]
              == metadata_a["instruction_count"])
        inventory = fixture.inventory(rom_a)
        check("fixture:inventory",
              inventory["phase6"]["status"] == "SUPPORTED_MMC1"
              and inventory["prg_bytes"] == 0x10000
              and inventory["chr_bytes"] == 0x2000
              and inventory["vectors"]["reset"] == 0xC000)
        check("fixture:three-sites",
              len(metadata_a["sites"]) == 3
              and metadata_a["exit_site"] == metadata_a["labels"]["run_exit"])
        FINDINGS["fixture"] = {
            "rom_sha256": metadata_a["rom_sha256"],
            "rom_size": metadata_a["rom_size"],
            "sites": metadata_a["sites"],
            "exit_site": metadata_a["exit_site"],
        }

        banner("bank_and_evidence")
        prg = rom_a[16:16 + inventory["prg_bytes"]]
        roots = [inventory["vectors"][name]
                 for name in ("reset", "nmi", "irq")]
        bank_report = bank_model.analyze(prg, metadata_a["prg_banks"], roots)
        check("bank:proven",
              bank_report["status"] == "OK"
              and bank_report["unresolved_instructions"] == 0
              and bank_report["proven_instructions"] == 50)
        identifiers: dict[int, list[dict]] = {}
        for entry in bank_report["instructions"]:
            identifiers.setdefault(entry["address"], []).append(entry)
        for site in metadata_a["sites"]:
            check(f"bank:site-{site:#06x}-proven",
                  identifiers.get(site) is not None
                  and all(item["bank"] == 1
                          and item["provenance"] == "PROVEN"
                          for item in identifiers[site]))
        image = fixture.cpu_image_for_bank(rom_a, inventory, 1)
        report = evidence.analyze_image(image, prg, metadata_a["prg_banks"],
                                        metadata_a["sites"],
                                        bank_identities=identifiers,
                                        roots=roots)
        check("evidence:counts",
              report["counts"] == {"RESOLVED_EXACT": 1,
                                   "RESOLVED_FINITE_SET": 1,
                                   "UNRESOLVED": 1})
        by_site = {record["site"]: record for record in report["sites"]}
        exact_site = metadata_a["sites"][0]
        finite_site = metadata_a["sites"][1]
        unresolved_site = metadata_a["sites"][2]
        check("evidence:exact-site",
              by_site[exact_site]["classification"] == "RESOLVED_EXACT"
              and by_site[exact_site]["bank_provenance"]["state"] == "PROVEN"
              and by_site[exact_site]["evaluated_banks"] == [1]
              and by_site[exact_site]["feasible_targets"]
              == [[1, metadata_a["labels"]["exact_target"]]])
        finite_targets = [metadata_a["labels"][name] for name in
                          ("finite_target_a", "finite_target_b",
                           "finite_target_c", "finite_target_d")]
        check("evidence:finite-site",
              by_site[finite_site]["classification"] == "RESOLVED_FINITE_SET"
              and by_site[finite_site]["index_domain"] == [0, 2, 4, 6]
              and [item[1] for item in
                   by_site[finite_site]["feasible_targets"]]
              == finite_targets)
        check("evidence:unresolved-site",
              by_site[unresolved_site]["classification"] == "UNRESOLVED"
              and by_site[unresolved_site]["feasible_targets"] == []
              and "not statically known" in by_site[unresolved_site]["reason"])
        FINDINGS["evidence"] = {
            "counts": report["counts"],
            "exact_target": by_site[exact_site]["feasible_targets"],
            "finite_targets": by_site[finite_site]["feasible_targets"],
            "unresolved_reason": by_site[unresolved_site]["reason"],
        }

        banner("reference_runs")
        runs = {}
        for selector in (0, 1, 2):
            patched = fixture.patched_rom(rom_a, metadata_a, selector)
            patched_inventory = fixture.inventory(patched)
            run = dispatch_reference.run(patched, patched_inventory,
                                         exit_site=metadata_a["exit_site"])
            expected = fixture.EXPECTED_MARKERS[selector]
            check(f"reference:selector-{selector}:exit",
                  run["exit_reached"] is True)
            check(f"reference:selector-{selector}:markers",
                  run["markers"]["marker"] == expected["kind"]
                  and run["markers"]["selector"] == expected["target"]
                  and run["markers"]["resume_out"] == expected["fixed"])
            runs[str(selector)] = {
                "markers": run["markers"],
                "steps": run["steps"],
                "clock": run["clock"],
                "executed_count": run["executed_count"],
            }
        check("differential:exact-target-executed",
              metadata_a["labels"]["exact_target"]
              in dispatch_reference.run(
                  fixture.patched_rom(rom_a, metadata_a, 0),
                  fixture.inventory(fixture.patched_rom(rom_a, metadata_a, 0)),
                  exit_site=metadata_a["exit_site"])["executed_addresses"])
        finite_patch = fixture.patched_rom(rom_a, metadata_a, 1)
        finite_run = dispatch_reference.run(
            finite_patch, fixture.inventory(finite_patch),
            exit_site=metadata_a["exit_site"])
        check("differential:finite-target-executed",
              fixture.EXPECTED_MARKERS[1]["target"] == 2
              and metadata_a["labels"]["finite_target_b"]
              in finite_run["executed_addresses"]
              and finite_targets[1] in finite_run["executed_addresses"])
        unresolved_patch = fixture.patched_rom(rom_a, metadata_a, 2)
        unresolved_run = dispatch_reference.run(
            unresolved_patch, fixture.inventory(unresolved_patch),
            exit_site=metadata_a["exit_site"])
        check("differential:unresolved-runtime-target",
              unresolved_run["markers"]["marker"] == 0
              and metadata_a["labels"]["fixed_target"]
              in unresolved_run["executed_addresses"])
        FINDINGS["reference_runs"] = runs

        banner("negative")
        for label, selector in (("negative-selector", -1),
                                ("boolean-selector", True)):
            try:
                fixture.patched_rom(rom_a, metadata_a, selector)
            except fixture.IndirectFixtureError:
                check(f"{label}:rejected", True)
            else:
                raise AssertionError(f"{label}:rejected")
        table = metadata_a["labels"]["finite_table"]
        tampered_prg = bytearray(prg)
        base = 1 * 0x4000 + (table - 0x8000)
        for offset in range(8):
            tampered_prg[base + offset] = 0x00
        tampered_report = evidence.analyze_image(
            image, bytes(tampered_prg), metadata_a["prg_banks"],
            [finite_site], bank_identities=identifiers, roots=roots)
        check("negative:impossible-table",
              tampered_report["sites"][0]["classification"] == "IMPOSSIBLE")
        try:
            evidence.analyze_image(b"\x00" * 16, prg, metadata_a["prg_banks"],
                                   metadata_a["sites"], roots=roots)
        except evidence.P7IndirectError:
            check("negative:short-image", True)
        else:
            raise AssertionError("negative:short-image")

        banner("regressions")
        regressions = []
        for script in REGRESSIONS:
            record = run_regression(script)
            check(f"regression:{script}:exit", record["returncode"] == 0)
            check(f"regression:{script}:stderr", record["stderr_empty"])
            regressions.append(record)
        p7_06_regression = run_regression(
            P7_06_GATE, ["--evidence-dir",
                         ".openrecomp-phase7/scratch/P7-07/regression_p7_06"])
        check("regression:p7-06:exit", p7_06_regression["returncode"] == 0)
        check("regression:p7-06:stderr", p7_06_regression["stderr_empty"])
        check("regression:p7-06:marker",
              any(marker == "OPENRECOMP_P7_06=PASS"
                  for marker in p7_06_regression["markers"]))
        regressions.append(p7_06_regression)
        FINDINGS["regressions"] = regressions

        banner("evidence")
        write_json("indirect_fixture.json", {
            "stage": STAGE,
            "fixture": {
                "name": metadata_a["fixture"],
                "license": metadata_a["license"],
                "sources": metadata_a["sources"],
                "source_sha256": metadata_a["source_sha256"],
                "rom_sha256": metadata_a["rom_sha256"],
                "rom_size": metadata_a["rom_size"],
                "prg_sha256": metadata_a["prg_sha256"],
                "chr_sha256": metadata_a["chr_sha256"],
                "prg_banks": metadata_a["prg_banks"],
                "chr_banks": metadata_a["chr_banks"],
                "vectors": inventory["vectors"],
                "sites": metadata_a["sites"],
                "exit_site": metadata_a["exit_site"],
                "selector_immediate_address":
                    metadata_a["selector_immediate_address"],
            },
            "bank_report": {
                "status": bank_report["status"],
                "proven_instructions": bank_report["proven_instructions"],
                "unresolved_instructions":
                    bank_report["unresolved_instructions"],
            },
            "evidence": {
                "counts": report["counts"],
                "sites": [
                    {key: record.get(key) for key in
                     ("site", "classification", "bank_provenance",
                      "evaluated_banks", "index_domain", "feasible_targets",
                      "infeasible_count", "reason", "definitions", "writes")}
                    for record in report["sites"]],
            },
            "reference_runs": runs,
            "expected_markers": metadata_a["expected_markers"],
            "claim": report["claim"],
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
    (EVIDENCE_DIR / "p7_07_tests.json").write_text(
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
