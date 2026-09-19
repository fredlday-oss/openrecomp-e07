#!/usr/bin/env python3
"""OpenRecomp Phase-7 translation-frontier integration gate (P7-08).

Integrates the proven P7-02..P7-07 results into the static recompilation
pipeline for the public fixtures: bank-aware reachability, indirect evidence
with explicit resolved target sets, data-region exclusion, path
specialization that stops at unresolved control flow, host emission only for
proven paths and a reproducible native build.

On success it emits::

    OPENRECOMP_P7_08=PASS
    OPENRECOMP_PHASE7_TRANSLATION_INTEGRATION_V1=PASS tests=<count>
    OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN
    OPENRECOMP_PHASE7_TMMT_PLAYABILITY=NOT_PROVEN

Usage:

    python tools/test_phase7_frontier_integration_v1.py \
        --evidence-dir .openrecomp-phase7/evidence/P7-08
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
import p7_classification_fixture_v1 as classification_fixture  # noqa: E402
import p7_frontier_integration_v1 as integration  # noqa: E402
import p7_indirect_evidence_v1 as evidence  # noqa: E402
import p7_indirect_flow_fixture_v1 as indirect_fixture  # noqa: E402
import p7_opcode_7c_v1 as opcode_module  # noqa: E402

STAGE = "P7-08"
STAGE_MARKER = "OPENRECOMP_P7_08"
FEATURE_MARKER = "OPENRECOMP_PHASE7_TRANSLATION_INTEGRATION_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE7_TMMT_PLAYABILITY"

P7_07_RECORD_REL = ".openrecomp-phase7/evidence/P7-07/p7_07_tests.json"
P7_07_GATE = "tools/test_phase7_indirect_fixture_v1.py"

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
        description="P7-08 translation-frontier integration gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase7/evidence/P7-08")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES, SCRATCH
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    SCRATCH = CONTROL7 / "scratch" / "P7-08"
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}

    print("=== P7-08 Translation Frontier Integration Gate ===", flush=True)
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
        check("anchor:p7-07-record-pass",
              read_json(ROOT / P7_07_RECORD_REL)["status"] == "PASS")
        check("anchor:decoder-unchanged", len(nes.OPCODES) == 151)

        banner("control_plane")
        state = (CONTROL7 / "STATE.md").read_text(encoding="utf-8")
        queue = (CONTROL7 / "STAGE_QUEUE.md").read_text(encoding="utf-8")
        check("control-plane:stage-row", "| P7-08 |" in queue)
        check("control-plane:terminal-reserved",
              f"{TERMINAL_MARKER}=NOT_PROVEN" in queue
              and f"{TERMINAL_MARKER}=NOT_PROVEN" in state)
        check("control-plane:compat-reserved",
              f"{COMPAT_MARKER}=NOT_PROVEN" in queue
              and f"{COMPAT_MARKER}=NOT_PROVEN" in state)
        check("control-plane:playability-reserved",
              f"{PLAYABILITY_MARKER}=NOT_PROVEN" in queue
              and f"{PLAYABILITY_MARKER}=NOT_PROVEN" in state)

        banner("indirect_fixture_integration")
        rom, metadata = indirect_fixture.build()
        inventory = indirect_fixture.inventory(rom)
        prg = rom[16:16 + inventory["prg_bytes"]]
        roots = [inventory["vectors"][name]
                 for name in ("reset", "nmi", "irq")]
        bank_report = bank_model.analyze(prg, metadata["prg_banks"], roots)
        identifiers: dict[int, list[dict]] = {}
        for entry in bank_report["instructions"]:
            identifiers.setdefault(entry["address"], []).append(entry)
        image = indirect_fixture.cpu_image_for_bank(rom, inventory, 1)
        evidence_report = evidence.analyze_image(
            image, prg, metadata["prg_banks"], metadata["sites"],
            bank_identities=identifiers, roots=roots)
        check("integration:evidence-counts",
              evidence_report["counts"] == {"RESOLVED_EXACT": 1,
                                             "RESOLVED_FINITE_SET": 1,
                                             "UNRESOLVED": 1})
        finite_site = metadata["sites"][1]
        unresolved_site = metadata["sites"][2]
        assignment = {finite_site: [1, metadata["labels"]["finite_target_b"]]}
        specialized = integration.specialize(
            prg, metadata["prg_banks"], roots, bank_report,
            evidence_report, assignment)
        check("integration:dispatch-resolved",
              specialized["dispatch"]
              == {f"1:0x{metadata['sites'][0]:04x}":
                  [1, metadata["labels"]["exact_target"]],
                  f"1:0x{finite_site:04x}":
                  [1, metadata["labels"]["finite_target_b"]]})
        check("integration:frontier-unresolved-only",
              specialized["frontier_count"] == 1
              and specialized["frontier"][0]["address"] == unresolved_site
              and specialized["frontier"][0]["classification"]
              == "UNRESOLVED")
        identity_addresses = {entry["address"]
                              for entry in specialized["identities"]}
        check("integration:unresolved-excluded",
              unresolved_site not in identity_addresses
              and metadata["labels"]["finite_target_b"] in identity_addresses
              and metadata["labels"]["run_exit"] in identity_addresses)
        check("integration:no-fabrication",
              all(entry["address"] >= 0x8000
                  for entry in specialized["identities"]))
        FINDINGS["indirect_integration"] = {
            "identity_count": specialized["identity_count"],
            "identity_digest": specialized["identity_digest"],
            "banks": specialized["banks"],
            "dynamic_nodes": specialized["dynamic_nodes"],
            "frontier": specialized["frontier"],
        }

        banner("host_emission")
        emission = integration.emit_host(
            rom, inventory, prg, metadata["prg_banks"], specialized, {
                "rom_sha256": metadata["rom_sha256"],
                "vectors": inventory["vectors"],
                "prg_banks": metadata["prg_banks"],
                "chr_banks": metadata["chr_banks"],
                "prg_size": inventory["prg_bytes"],
                "chr_size": inventory["chr_bytes"],
            })
        check("emit:deterministic",
              integration.emit_host(
                  rom, inventory, prg, metadata["prg_banks"], specialized, {
                      "rom_sha256": metadata["rom_sha256"],
                      "vectors": inventory["vectors"],
                      "prg_banks": metadata["prg_banks"],
                      "chr_banks": metadata["chr_banks"],
                      "prg_size": inventory["prg_bytes"],
                      "chr_size": inventory["chr_bytes"],
                  })["host_program_sha256"]
              == emission["host_program_sha256"])
        check("emit:proven-paths-only",
              f"case 0x{unresolved_site:04X}u:" not in emission["host_program"]
              and f"case 0x{metadata['labels']['exact_target']:04X}u:"
              in emission["host_program"]
              and f"case 0x{metadata['labels']['finite_target_b']:04X}u:"
              in emission["host_program"])
        FINDINGS["emission"] = {
            "instructions": emission["instructions"],
            "host_program_sha256": emission["host_program_sha256"],
            "support_sha256": emission["support_sha256"],
        }

        banner("native_build")
        workspace = SCRATCH / "build"
        comparison = integration.build_native(
            emission, fixture_id="p7-08-indirect-fixture", workspace=workspace)
        check("build:classification",
              comparison.classification.name == "EXECUTABLE_REPRODUCIBLE"
              and comparison.executable_reproducible is True
              and comparison.manifest_reproducible is True)
        executable = workspace / "run1" / "program.exe"
        check("build:executable-present", executable.is_file())
        executable_sha256 = sha256_bytes(executable.read_bytes())
        check("build:toolchain",
              all(run.manifest.build_status.name == "OK"
                  for run in comparison.runs))
        FINDINGS["build"] = {"executable_sha256": executable_sha256}

        banner("classification_data_exclusion")
        classification_rom, classification_metadata = \
            classification_fixture.build()
        classification_inventory = classification_fixture.inventory(
            classification_rom)
        classification_prg = classification_rom[
            16:16 + classification_inventory["prg_bytes"]]
        classification_roots = [
            classification_inventory["vectors"][name]
            for name in ("reset", "nmi", "irq")]
        classification_image = classification_fixture.cpu_image(
            classification_rom, classification_inventory)
        classification_record = opcode_module.classify(
            classification_image,
            classification_metadata["mechanism"]["table_base"],
            classification_roots)
        check("classification:data-not-code",
              classification_record["classification"] == "DATA_NOT_CODE")
        bank_blocked = bank_model.analyze(
            classification_prg, classification_metadata["prg_banks"],
            classification_roots)
        check("classification:frontier-fail-closed",
              bank_blocked["status"] == "BLOCKED_UNDECODABLE"
              and bank_blocked["stop"]["address"]
              == classification_metadata["mechanism"]["table_base"])
        FINDINGS["classification_exclusion"] = {
            "classification": classification_record["classification"],
            "bank_status": bank_blocked["status"],
            "stop": bank_blocked["stop"],
        }

        banner("negative")
        bad_assignment = {finite_site: [1, 0xC999]}
        bad = integration.specialize(
            prg, metadata["prg_banks"], roots, bank_report,
            evidence_report, bad_assignment)
        check("negative:bad-assignment-fail-closed",
              bad["frontier_count"] >= 1
              and any("not in the proven feasible set" in entry["reason"]
                      for entry in bad["frontier"]))
        tampered_prg = bytearray(prg)
        base = 1 * 0x4000 + (metadata["labels"]["finite_table"] - 0x8000)
        for offset in range(8):
            tampered_prg[base + offset] = 0x11
        tampered_report = evidence.analyze_image(
            image, bytes(tampered_prg), metadata["prg_banks"],
            [finite_site], bank_identities=identifiers, roots=roots)
        check("negative:tampered-table-infeasible",
              tampered_report["sites"][0]["classification"]
              in ("IMPOSSIBLE", "UNRESOLVED"))

        banner("regressions")
        regressions = []
        for script in REGRESSIONS:
            record = run_regression(script)
            check(f"regression:{script}:exit", record["returncode"] == 0)
            check(f"regression:{script}:stderr", record["stderr_empty"])
            regressions.append(record)
        p7_07_regression = run_regression(
            P7_07_GATE, ["--evidence-dir",
                         ".openrecomp-phase7/scratch/P7-08/regression_p7_07"])
        check("regression:p7-07:exit", p7_07_regression["returncode"] == 0)
        check("regression:p7-07:stderr", p7_07_regression["stderr_empty"])
        check("regression:p7-07:marker",
              any(marker == "OPENRECOMP_P7_07=PASS"
                  for marker in p7_07_regression["markers"]))
        regressions.append(p7_07_regression)
        FINDINGS["regressions"] = regressions

        banner("evidence")
        write_json("translation_frontier.json", {
            "stage": STAGE,
            "indirect_fixture": {
                "rom_sha256": metadata["rom_sha256"],
                "sites": metadata["sites"],
                "bank_report": {
                    "status": bank_report["status"],
                    "proven_instructions":
                        bank_report["proven_instructions"],
                },
                "evidence_counts": evidence_report["counts"],
                "specialization": FINDINGS["indirect_integration"],
                "emission": FINDINGS["emission"],
                "native_build": FINDINGS["build"],
            },
            "classification_fixture": FINDINGS["classification_exclusion"],
            "frontier_recomputation": {
                "proven_identities": specialized["identity_count"],
                "resolved_dispatch_sites": len(specialized["dispatch"]),
                "fail_closed_sites": specialized["frontier_count"],
                "excluded_bank_identities": sorted(
                    {f"{entry['bank']}:0x{entry['address']:04x}"
                     for entry in bank_report["instructions"]}
                    - {f"{entry['bank']}:0x{entry['address']:04x}"
                       for entry in specialized["identities"]}),
                "note": "path specialization follows proven resolved targets "
                        "and stops at unresolved indirect sites; unresolved "
                        "sites are excluded from emission (fail closed)",
            },
            "claim":
                "host code is emitted only for proven executable paths; "
                "resolved indirect dispatches are specialized to their "
                "proven targets and unresolved control flow is excluded",
            "public_claim": metadata["public_claim"],
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
    (EVIDENCE_DIR / "p7_08_tests.json").write_text(
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
