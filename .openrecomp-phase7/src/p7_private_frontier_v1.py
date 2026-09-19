#!/usr/bin/env python3
"""Phase-7 private TMNT frontier run with Phase-7 support (P7-11).

Re-runs the frozen Phase-6 private pipeline plus the Phase-7 machinery
(classification, bank-aware reachability, indirect evidence) and records the
exact frontier delta by hashes/metadata/derived evidence only:

* `0xC570` blocker: the bank-aware walk still stops there, but the byte is now
  classified `DATA_NOT_CODE` with a proven inline dispatch table and a code
  resume address - the closure rule that would skip it is *not* applied here
  (P7-12 is evidence-driven by this record);
* the three `$E2` sites: explicit `RESOLVED_FINITE_SET` evidence with
  per-site bank provenance and bounded target counts;
* bank-window frontier: proven and unresolved-limited candidate identities
  across all physical banks instead of the power-on-only candidates;
* translation/native: still not attempted without a complete proven frontier.

No ROM bytes are read into evidence; only hashes, metadata, addresses, counts
and classifications are recorded.
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

import p6_private_fixture_v1 as private_fixture  # noqa: E402
import p6_private_run_v1 as private_run  # noqa: E402
import p7_bank_reachability_v1 as bank_model  # noqa: E402
import p7_indirect_evidence_v1 as indirect_evidence  # noqa: E402
import p7_opcode_7c_v1 as classification  # noqa: E402

P6_10_PIPELINE_REL = ".openrecomp-phase6/evidence/P6-10/tmnt_pipeline.json"
P6_10_PIPELINE_SHA256 = (
    "0b8c9014fa11f9e363f1cfb1c569048f786b8baec2117769adb862b375a3ebdc")

BANK_BUDGET = 300000
UNRESOLVED_LIMIT = 20000


class P7PrivateFrontierError(ValueError):
    """Fail-closed private frontier error."""


def run(path: pathlib.Path | str = private_fixture.PRIVATE_ROM) -> dict[str, Any]:
    location = pathlib.Path(path)
    if not location.is_file():
        raise P7PrivateFrontierError(
            "private compatibility fixture is not present")
    data = location.read_bytes()
    image, inventory = classification.build_image(data)
    prg_bytes = int(inventory["prg_bytes"])
    prg_banks = prg_bytes // bank_model.PRG_BANK_BYTES
    roots = [inventory["vectors"][name] for name in ("reset", "nmi", "irq")]
    prg = data[16:16 + prg_bytes]

    pipeline = private_run.run(location)
    bank_report = bank_model.analyze(prg, prg_banks, roots,
                                     budget=BANK_BUDGET,
                                     unresolved_limit=UNRESOLVED_LIMIT)
    indirect = indirect_evidence.analyze_private(location)
    classified = classification.run(location)

    p6_10_path = ROOT / P6_10_PIPELINE_REL
    if not p6_10_path.is_file():
        raise P7PrivateFrontierError("the committed P6-10 record is missing")
    if hashlib.sha256(p6_10_path.read_bytes()).hexdigest() != P6_10_PIPELINE_SHA256:
        raise P7PrivateFrontierError("the committed P6-10 record changed")
    p6_10 = json.loads(p6_10_path.read_text(encoding="utf-8"))
    p6_candidate = p6_10["frontier"]["candidate"]

    sites = []
    for record in indirect["sites"]:
        sites.append({
            "site": record["site"],
            "classification": record["classification"],
            "bank_provenance": record["bank_provenance"]["state"],
            "proven_banks": record["bank_provenance"]["proven_banks"],
            "candidate_banks": record["bank_provenance"]["candidate_banks"],
            "evaluated_banks": record.get("evaluated_banks"),
            "index_domain_size": record.get("index_domain_size"),
            "feasible_target_count": len(record.get("feasible_targets", [])),
            "infeasible_count": record.get("infeasible_count"),
        })

    deltas = {
        "c570_blocker": {
            "p6_status": "BLOCKED_UNSUPPORTED_OPCODE",
            "p7_status": "PERSISTS_CLASSIFIED_AS_DATA_NOT_CODE",
            "p7_classification": classified["classification"],
            "table_entries": classified["inline_table"]["entries"],
            "table_byte_length": classified["inline_table"]["byte_length"],
            "resume_address": classified["inline_table"]["resume_address"],
            "closure_applied": False,
            "note": "the frontier walk still stops at the classified data "
                    "table; the evidence-backed closure rule is left to P7-12",
        },
        "e2_sites": {
            "p6_status": "UNRESOLVED_INDIRECT_JUMP",
            "p7_status": "ALL_RESOLVED_FINITE_SET",
            "sites": sites,
            "note": "each site now carries an explicit proven value-source "
                    "chain and a finite feasible target set",
        },
        "bank_window_frontier": {
            "p6_candidate_instructions": p6_candidate["instructions"],
            "p6_low_window_instructions":
                p6_candidate["low_window_instructions"],
            "p7_proven_instructions": bank_report["proven_instructions"],
            "p7_unresolved_instructions":
                bank_report["unresolved_instructions"],
            "p7_unresolved_limited": bank_report["unresolved_limited"],
            "p7_banks": len(bank_report["code_by_bank"]),
            "delta": "EXPANDED",
        },
        "translation": {
            "status": "NOT_ATTEMPTED",
            "reason": "the proven frontier is incomplete (classified data "
                      "table not skipped, unresolved bank candidates remain)",
        },
        "native_build": {"status": "NOT_ATTEMPTED"},
        "native_execution": {"status": "NOT_ATTEMPTED"},
    }
    return {
        "stage": "P7-11",
        "classification": "PRIVATE_LOCAL_COMPATIBILITY_FIXTURE",
        "source_path": str(location),
        "image_sha256": inventory["image_sha256"],
        "image_size": inventory["actual_size"],
        "prg_banks": prg_banks,
        "p6_frontier": {
            "stop_address": p6_candidate["stop"]["address"],
            "stop_reason": p6_candidate["stop"]["reason"],
            "candidate_instructions": p6_candidate["instructions"],
            "low_window_instructions":
                p6_candidate["low_window_instructions"],
            "indirect_sites": [item["address"]
                               for item in p6_candidate["indirect_sites"]],
        },
        "p7_bank_frontier": {
            "status": bank_report["status"],
            "stop": bank_report["stop"],
            "nodes_visited": bank_report["nodes_visited"],
            "proven_instructions": bank_report["proven_instructions"],
            "unresolved_instructions": bank_report["unresolved_instructions"],
            "unresolved_limited": bank_report["unresolved_limited"],
            "code_by_bank": [
                {"bank": entry["bank"],
                 "proven": entry["proven_instructions"],
                 "unresolved": entry["unresolved_instructions"]}
                for entry in bank_report["code_by_bank"]],
        },
        "classification_0xc570": {
            "classification": classified["classification"],
            "inline_table": classified["inline_table"],
            "code_resume": classified["code_resume"],
            "semantics_added": classified["semantics_added"],
        },
        "indirect_evidence": {
            "counts": indirect["counts"],
            "sites": sites,
        },
        "p6_pipeline_translation_status": pipeline["translation"]["status"],
        "p6_pipeline_native_build_status": pipeline["native_build"]["status"],
        "deltas": deltas,
        "blockers": [
            {"code": "BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE",
             "stage": "frontier",
             "detail": "classified data table at 0xC570 not yet skipped: "
                       "needs the evidence-backed closure rule"},
            {"code": "BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE",
             "stage": "bank_state",
             "detail": f"{bank_report['unresolved_instructions']} unresolved "
                       "candidate identities across banks remain (bounded "
                       "expansion)"},
            {"code": "NOT_TESTED",
             "stage": "runtime_platform",
             "detail": "platform behaviour remains untestable until a complete "
                       "proven translation exists"},
        ],
        "public_claim": "none; private local analysis must not enter the "
                        "public package",
    }


__all__ = ["P7PrivateFrontierError", "run"]
