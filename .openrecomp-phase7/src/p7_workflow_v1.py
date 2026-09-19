#!/usr/bin/env python3
"""Phase-7 reusable bank-aware ROM-to-native workflow (P7-14).

One deterministic entry point accepts a local ROM path and produces:

* inventory and compatibility classification (never copying the ROM);
* a bank-aware reachable frontier with explicit proven/unresolved identities;
* indirect-control-flow classification for the discovered `$E2` sites;
* the evidence-driven inline-dispatch closure;
* generated native source and a reproducible build when the proven frontier
  supports it (resolved dispatch targets are specialized deterministically);
* explicit fail-closed blockers otherwise.

The original guest image is never executed on the host and never written into
the workspace as a ROM-extension file.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for entry in (str(ROOT), str(ROOT / "tools"),
              str(ROOT / ".openrecomp-phase5" / "src"),
              str(ROOT / ".openrecomp-phase6" / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import p6_ines_v1 as ingestion  # noqa: E402
import p7_bank_reachability_v1 as bank_model  # noqa: E402
import p7_frontier_integration_v1 as integration  # noqa: E402
import p7_indirect_evidence_v1 as indirect_evidence  # noqa: E402
import p7_inline_closure_v1 as closure  # noqa: E402

WORKFLOW_ID = "p7_rom_to_native_v1"
ASSIGNMENT_POLICY = "lowest_target"
BANK_BUDGET = 300000
UNRESOLVED_LIMIT = 20000
POINTER = 0xE2
EXIT_POINTER = 0x02FF


class P7WorkflowError(ValueError):
    """Fail-closed workflow error."""


def _blocker(code: str, stage: str, classification: str,
             detail: str) -> dict[str, str]:
    return {"code": code, "stage": stage, "classification": classification,
            "detail": detail}


def run(path: pathlib.Path | str, *, workspace: pathlib.Path | str,
        build: bool = True) -> dict[str, Any]:
    location = pathlib.Path(path)
    if not location.is_file():
        raise P7WorkflowError("ROM path is not present")
    data = location.read_bytes()
    try:
        inventory = ingestion.ingest(data, source_label="workflow")
    except Exception as exc:  # noqa: BLE001 - deterministic classification
        return {
            "workflow": WORKFLOW_ID,
            "stage": "P7-14",
            "status": "FAIL_CLOSED",
            "input": {
                "source_path": str(location),
                "image_sha256": hashlib.sha256(data).hexdigest(),
                "image_size": len(data),
                "source_rom_copied": False,
            },
            "inventory": {"status": "REJECTED"},
            "blockers": [_blocker("MALFORMED_CONTAINER", "ingestion",
                                  "malformed_input",
                                  f"{type(exc).__name__}: {exc}")],
            "public_claim": "none",
        }
    blockers: list[dict[str, str]] = []
    if inventory["phase6"]["status"] != "SUPPORTED_MMC1":
        return {
            "workflow": WORKFLOW_ID,
            "stage": "P7-14",
            "status": "FAIL_CLOSED",
            "input": {
                "source_path": str(location),
                "image_sha256": inventory["image_sha256"],
                "image_size": inventory["actual_size"],
                "source_rom_copied": False,
            },
            "inventory": {
                "status": inventory["phase6"]["status"],
                "container": inventory["container"],
                "mapper": inventory["mapper"],
                "submapper": inventory["submapper"],
                "mirroring": inventory["mirroring"],
            },
            "blockers": [_blocker("UNSUPPORTED_CARTRIDGE", "inventory",
                                  "unsupported_mapper",
                                  inventory["phase6"]["reasons"][0]
                                  if inventory["phase6"]["reasons"]
                                  else "cartridge is outside the supported "
                                       "subset")],
            "public_claim": "none",
        }
    prg_bytes = int(inventory["prg_bytes"])
    prg_banks = prg_bytes // bank_model.PRG_BANK_BYTES
    prg = data[16:16 + prg_bytes]
    roots = [inventory["vectors"][name] for name in ("reset", "nmi", "irq")]
    bank_report = bank_model.analyze(prg, prg_banks, roots,
                                     budget=BANK_BUDGET,
                                     unresolved_limit=UNRESOLVED_LIMIT)
    identifiers: dict[int, list[dict]] = {}
    for entry in bank_report["instructions"]:
        identifiers.setdefault(entry["address"], []).append(entry)
    run_exit_sites = [item["address"]
                      for item in bank_report["indirect_sites"]
                      if item.get("pointer") == EXIT_POINTER]
    e2_sites = [item["address"] for item in bank_report["indirect_sites"]
                if item.get("pointer") == POINTER]
    other_sites = [item["address"] for item in bank_report["indirect_sites"]
                   if item.get("pointer") not in (POINTER, EXIT_POINTER)]
    image = integration._image_for_context(prg, prg_banks, 0)
    site_records: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for site in e2_sites:
        identities = identifiers.get(site, [])
        proven = sorted({entry["bank"] for entry in identities
                         if entry["provenance"] == "PROVEN"})
        bank = proven[0] if len(proven) == 1 else 0
        site_image = integration._image_for_context(prg, prg_banks, bank)
        single = indirect_evidence.analyze_image(
            site_image, prg, prg_banks, [site],
            bank_identities=identifiers, roots=roots)
        site_records.extend(single["sites"])
        for state, value in single["counts"].items():
            counts[state] = counts.get(state, 0) + value
    indirect_report = {"counts": dict(sorted(counts.items())),
                       "sites": site_records}
    closed = closure.analyze(image, roots)

    report: dict[str, Any] = {
        "workflow": WORKFLOW_ID,
        "stage": "P7-14",
        "input": {
            "source_path": str(location),
            "source_classification": "PUBLIC_OR_USER_SUPPLIED_LOCAL_ROM",
            "image_sha256": inventory["image_sha256"],
            "image_size": inventory["actual_size"],
            "source_rom_copied": False,
        },
        "inventory": {
            "status": "OK",
            "container": inventory["container"],
            "mapper": inventory["mapper"],
            "submapper": inventory["submapper"],
            "mirroring": inventory["mirroring"],
            "prg_bytes": prg_bytes,
            "chr_bytes": inventory["chr_bytes"],
            "prg_banks_16k": prg_banks,
            "vectors": inventory["vectors"],
        },
        "bank_frontier": {
            "status": bank_report["status"],
            "stop": bank_report["stop"],
            "proven_instructions": bank_report["proven_instructions"],
            "unresolved_instructions":
                bank_report["unresolved_instructions"],
            "unresolved_limited": bank_report["unresolved_limited"],
            "code_by_bank": [
                {"bank": entry["bank"],
                 "proven": entry["proven_instructions"],
                 "unresolved": entry["unresolved_instructions"]}
                for entry in bank_report["code_by_bank"]],
        },
        "indirect_control_flow": {
            "pointer": f"0x{POINTER:02x}",
            "run_exit_sites": sorted(run_exit_sites),
            "counts": indirect_report["counts"],
            "sites": [
                {"site": record["site"],
                 "classification": record["classification"],
                 "bank_provenance": (record.get("bank_provenance") or {})
                 .get("state", "NOT_ANALYZED"),
                 "feasible_targets": record.get("feasible_targets", []),
                 "reason": record.get("reason")}
                for record in indirect_report["sites"]],
            "unsupported_pointers": sorted(other_sites),
        },
        "inline_closure": {
            "tables": closed["tables"],
            "instructions": closed["closure"]["instructions"],
            "stop": closed["closure"]["stop"],
        },
    }
    if other_sites:
        blockers.append(_blocker(
            "UNSUPPORTED_INDIRECT_POINTER", "indirect_control_flow",
            "unsupported_pointer",
            "indirect sites with pointers other than 0x00E2 are not resolved: "
            + ", ".join(f"0x{site:04x}" for site in other_sites)))
    if bank_report["status"] != "OK":
        blockers.append(_blocker(
            "BANK_FRONTIER_INCOMPLETE", "bank_state",
            "unresolved_bank_provenance",
            f"bank-aware frontier is {bank_report['status']} at "
            f"0x{bank_report['stop']['address']:04x} with "
            f"{bank_report['unresolved_instructions']} unresolved-limited "
            "candidate identities"))
    assignment: dict[int, list[int]] = {}
    for record in indirect_report["sites"]:
        if record["classification"] in ("RESOLVED_EXACT",
                                        "RESOLVED_FINITE_SET") \
                and record.get("feasible_targets"):
            assignment[record["site"]] = list(record["feasible_targets"][0])
        else:
            blockers.append(_blocker(
                "UNRESOLVED_INDIRECT_SITE", "indirect_control_flow",
                "unresolved_indirect_control_flow",
                f"site 0x{record['site']:04x} is "
                f"{record['classification']}: "
                f"{record.get('reason', 'no feasible targets')}"))
    if bank_report["status"] != "OK" or other_sites:
        report["status"] = "FAIL_CLOSED"
        report["blockers"] = blockers
        report["translation"] = {"status": "NOT_ATTEMPTED"}
        report["generated_sources"] = {"status": "NOT_GENERATED"}
        report["native_build"] = {"status": "NOT_ATTEMPTED"}
        report["public_claim"] = "none"
        return report

    specialized = integration.specialize(prg, prg_banks, roots, bank_report,
                                         indirect_report, assignment)
    report["specialization"] = {
        "identity_count": specialized["identity_count"],
        "identity_digest": specialized["identity_digest"],
        "banks": specialized["banks"],
        "dispatch": specialized["dispatch"],
        "frontier": specialized["frontier"],
        "assignment_policy": ASSIGNMENT_POLICY,
    }
    try:
        emission = integration.emit_host(
            data, inventory, prg, prg_banks, specialized, {
                "rom_sha256": inventory["image_sha256"],
                "vectors": inventory["vectors"],
                "prg_banks": prg_banks,
                "chr_banks": int(inventory["chr_bytes"]) // 0x2000,
                "prg_size": prg_bytes,
                "chr_size": int(inventory["chr_bytes"]),
            })
    except Exception as exc:  # noqa: BLE001 - deterministic fail-closed
        blockers.append(_blocker("EMISSION_UNSUPPORTED", "translation",
                                 "emission_failed",
                                 f"{type(exc).__name__}: {exc}"))
        report["status"] = "FAIL_CLOSED"
        report["blockers"] = blockers
        report["generated_sources"] = {"status": "NOT_GENERATED"}
        report["native_build"] = {"status": "NOT_ATTEMPTED"}
        report["public_claim"] = "none"
        return report
    report["generated_sources"] = {
        "status": "GENERATED",
        "instructions": emission["instructions"],
        "host_program_sha256": emission["host_program_sha256"],
        "support_sha256": emission["support_sha256"],
    }
    report["translation"] = {
        "status": "TRANSLATED",
        "fail_closed_sites": len(specialized["frontier"]),
        "runtime_fail_closed":
            "unresolved sites are excluded from the host program and fail "
            "closed at runtime",
    }
    if not blockers:
        report["status"] = "COMPLETED"
    else:
        report["status"] = "COMPLETED_WITH_FRONTIER"
    report["blockers"] = blockers
    if build:
        workspace_path = pathlib.Path(workspace)
        workspace_path.mkdir(parents=True, exist_ok=True)
        try:
            comparison = integration.build_native(
                emission, fixture_id=f"{WORKFLOW_ID}-{inventory['image_sha256'][:12]}",
                workspace=workspace_path)
            executable = workspace_path / "run1" / "program.exe"
            report["native_build"] = {
                "status": "BUILT",
                "classification": comparison.classification.name,
                "executable_reproducible":
                    comparison.executable_reproducible,
                "executable_sha256": hashlib.sha256(
                    executable.read_bytes()).hexdigest()
                if executable.is_file() else None,
            }
        except Exception as exc:  # noqa: BLE001 - deterministic fail-closed
            report["native_build"] = {
                "status": "FAIL_CLOSED",
                "reason": f"{type(exc).__name__}: {exc}",
            }
            blockers.append(_blocker("NATIVE_BUILD_UNSUPPORTED", "native_build",
                                     "build_failed",
                                     f"{type(exc).__name__}: {exc}"))
            report["status"] = "FAIL_CLOSED"
    else:
        report["native_build"] = {"status": "NOT_REQUESTED"}
    report["public_claim"] = (
        "bounded audited recompilation of the supplied local image only; no "
        "general compatibility claim")
    return report


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Phase-7 ROM-to-native workflow")
    parser.add_argument("rom")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--no-build", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = run(args.rom, workspace=args.workspace,
                     build=not args.no_build)
    except P7WorkflowError as exc:
        print(json.dumps({"workflow": WORKFLOW_ID, "status": "FAIL_CLOSED",
                          "error": str(exc)}, indent=2, sort_keys=True))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


__all__ = ["P7WorkflowError", "WORKFLOW_ID", "run"]


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
