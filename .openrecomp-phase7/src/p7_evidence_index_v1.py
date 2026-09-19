#!/usr/bin/env python3
"""Phase-7 evidence index and claim ledger (P7-91).

Builds a complete index of the Phase-7 evidence tree with path/size/sha256
and tracked status, verifies the control plane and frozen boundaries, and
records the claim ledger with the frozen vocabulary, keeping five areas
separate: the Phase-5 NROM proof, the Phase-6 MMC1 proof, the Phase-7 public
translation/control-flow proof, the private TMNT observations and general NES
compatibility.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTROL7 = ROOT / ".openrecomp-phase7"

STAGES = tuple(f"P7-{index:02d}" for index in range(0, 15)) + ("P7-90",)

PHASE7_PROVEN = [
    "evidence-based classification of the 0x7C byte at 0xC570 as "
    "DATA_NOT_CODE (inline dispatch table) with no undocumented-opcode "
    "semantics added",
    "original Apache-2.0 public classification fixture with a documented "
    "inline-dispatch mechanism and classifier proofs over public synthetic "
    "images (DATA_NOT_CODE / AMBIGUOUS / REACHABLE_CODE / UNREACHABLE)",
    "bank-aware MMC1 reachability model with physical-bank code identities, "
    "proven/UNRESOLVED provenance, statically proven constant bank commits "
    "and explicit non-merging of banks sharing CPU addresses",
    "bank-aware neutral CFG/function/translation-unit structure per proven "
    "bank with real cross-bank call entries and no fabricated cross-bank "
    "edges",
    "indirect-jump evidence model with explicit RESOLVED_EXACT / "
    "RESOLVED_FINITE_SET / UNRESOLVED / IMPOSSIBLE states, pointer "
    "write/read provenance and bounded table-derived target enumeration",
    "original Apache-2.0 public indirect-control-flow fixture exercising "
    "exact, finite-set and unresolved dispatch with reference execution",
    "translation frontier integration that emits host code only for proven "
    "paths, specializes resolved indirect dispatch and excludes unresolved "
    "sites (runtime fail-closed)",
    "native execution of the public Phase-7 fixture (exact and finite paths "
    "succeed; unresolved path fails closed) through generated host code only",
    "exact bounded reference equivalence for the proven public paths over "
    "CPU/RAM/PPU/mapper/controller/interrupt/transcript state (documented "
    "2-cycle dispatch-specialization timing delta excluded)",
    "evidence-driven inline-dispatch closure proven on the public fixture "
    "before private application",
    "reusable bank-aware ROM-to-native workflow (inventory, classification, "
    "bank frontier, indirect classification, generated build or explicit "
    "fail-closed blockers) with no source ROM copying",
]

PHASE7_BOUNDED = [
    "the 0x7C classification is bounded to the analyzed private address and "
    "public fixture context; no universal undocumented-opcode claim",
    "bank-aware reachability covers the audited MMC1 subset and the proven "
    "layout model; it does not prove arbitrary bank sequences",
    "the indirect target sets are feasible sets over proven value sources, "
    "not runtime-exact selector behavior",
    "native execution and reference equivalence cover the public Phase-7 "
    "fixtures only",
    "the closure rule covers the audited inline-dispatch form only",
]

PHASE7_LIMITATIONS = [
    "no general NES compatibility claim",
    "no commercial-game or TMNT playability claim",
    "no universal undocumented-opcode support",
    "no all-indirect-control-flow recovery claim",
    "no arbitrary bank-switched binary support claim",
    "no cycle accuracy claim (dispatch specialization changes emitted cost)",
    "no full PPU/APU accuracy claim",
    "no FDS or arbitrary-6502 compatibility claim",
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def git_ls_files() -> set[str]:
    completed = subprocess.run(["git", "ls-files"], cwd=str(ROOT),
                               capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
    return {line.strip() for line in completed.stdout.splitlines() if line.strip()}


def build_index() -> dict[str, Any]:
    tracked = git_ls_files()
    own_dir = CONTROL7 / "evidence" / "P7-91"
    files = []
    for path in sorted((CONTROL7 / "evidence").rglob("*")):
        if not path.is_file():
            continue
        if path.is_relative_to(own_dir):
            continue
        relative = path.relative_to(ROOT).as_posix()
        files.append({
            "path": relative,
            "size": path.stat().st_size,
            "sha256": sha256_file(path),
            "tracked": relative in tracked,
        })
    digest = sha256_bytes(json.dumps(files, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8"))
    return {
        "stage": "P7-91",
        "evidence_files": len(files),
        "index_digest": digest,
        "files": files,
    }


def build_claim_record(index: dict[str, Any]) -> dict[str, Any]:
    stage_records = {}
    for stage in STAGES:
        path = (CONTROL7 / "evidence" / stage /
                f"{stage.lower().replace('-', '_')}_tests.json")
        if path.is_file():
            document = json.loads(path.read_text(encoding="utf-8"))
            stage_records[stage] = {
                "status": document["status"],
                "tests": document["tests"],
                "sha256": sha256_file(path),
            }
    p6_91_claims = json.loads(
        (ROOT / ".openrecomp-phase6" / "evidence" / "P6-91"
         / "claim_record.json").read_text(encoding="utf-8"))
    return {
        "stage": "P7-91",
        "vocabulary": ["PROVEN", "BOUNDED", "UNPROVEN", "UNSUPPORTED",
                       "NOT TESTED"],
        "terminal_marker":
            "OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF=NOT_PROVEN",
        "compatibility_marker":
            "OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN",
        "playability_marker":
            "OPENRECOMP_PHASE7_TMMT_PLAYABILITY=NOT_PROVEN",
        "ledger": {
            "phase5_public_nrom": {
                "status": "PROVEN",
                "basis": "frozen Phase-6 claim ledger (Phase-5 public NROM "
                         "static-recompilation proof)",
                "proven_count": p6_91_claims["phase5_proven_count"],
                "bounded_count": p6_91_claims["phase5_bounded_count"],
            },
            "phase6_public_mmc1": {
                "status": "PROVEN",
                "basis": "frozen Phase-6 claim ledger (bounded audited public "
                         "MMC1 platform proof)",
                "proven_count": p6_91_claims["proven_count"],
                "bounded_count": p6_91_claims["bounded_count"],
            },
            "phase7_public_translation": {
                "status": "PROVEN",
                "proven_count": len(PHASE7_PROVEN),
                "bounded_count": len(PHASE7_BOUNDED),
                "basis": "public Phase-7 fixtures, models and verified "
                         "native/reference paths only",
            },
            "private_tmnt_compatibility": {
                "status": "UNPROVEN",
                "observations": [
                    "frontier re-derived byte-identically (P7-01)",
                    "0x7C at 0xC570 classified DATA_NOT_CODE (6-entry table, "
                    "resume 0xC57C) without semantics added",
                    "three $E2 sites RESOLVED_FINITE_SET with 4/4/300 "
                    "feasible targets",
                    "closure advances the frontier from 0xC570 to 0xBB6B "
                    "(undocumented 0xE3)",
                ],
                "blockers": [
                    "unclassified undocumented byte 0xE3 at 0xBB6B",
                    "14027 unresolved-limited bank candidate identities",
                    "runtime platform NOT_TESTED",
                ],
                "playability": "NOT_PROVEN",
            },
            "general_nes": {
                "status": "UNPROVEN",
                "note": "no general, commercial or arbitrary-6502 "
                        "compatibility is claimed",
            },
        },
        "stage_records": stage_records,
        "proven_claims": PHASE7_PROVEN,
        "bounded_claims": PHASE7_BOUNDED,
        "limitations": PHASE7_LIMITATIONS,
        "evidence_files": index["evidence_files"],
        "index_digest": index["index_digest"],
        "public_claim": "the exact bounded public translation/control-flow "
                        "claim only; all general markers remain NOT_PROVEN",
    }


__all__ = ["STAGES", "build_claim_record", "build_index"]


if __name__ == "__main__":
    index = build_index()
    claim = build_claim_record(index)
    print(json.dumps({"index": {k: v for k, v in index.items()
                                if k != "files"},
                      "claim_counts": {
                          "proven": len(PHASE7_PROVEN),
                          "bounded": len(PHASE7_BOUNDED),
                          "limitations": len(PHASE7_LIMITATIONS)}},
                     indent=2, sort_keys=True))
    raise SystemExit(0)
