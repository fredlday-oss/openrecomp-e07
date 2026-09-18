#!/usr/bin/env python3
"""Phase-5 evidence index and claim ledger (P5-91).

Builds the complete Phase-5 evidence index (every stage evidence file with
size/sha256/tracked status, control-plane hashes, frozen boundary identities,
package identity) and the explicit claim ledger separating PROVEN, BOUNDED,
UNPROVEN, UNSUPPORTED and NOT TESTED, with the legal public fixture result,
the private TMNT observations and general NES compatibility in separate
sections.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = ROOT / ".openrecomp-phase5" / "evidence"
CONTROL = ROOT / ".openrecomp-phase5"
PACKAGE = CONTROL / "package" / "phase5_nes_package_v1.zip"

STAGES = tuple(f"P5-{index:02d}"
               for index in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 90))

CONTROL_FILES = (
    "CONTROL_POLICY.md", "EVIDENCE_SCHEMA.md", "FIXTURE_POLICY.md",
    "HANDOFF.md", "SCOPE.md", "SOURCE_SHA256SUMS.txt", "STAGE_QUEUE.md",
    "STATE.md",
)

BOUNDARIES = {
    "phase4_tag": "openrecomp-phase4-pass",
    "phase4_tag_object": "e7eaab18fee267b3d7962db13835c9e14dd77fc2",
    "phase4_commit": "b3c71fb690f00b4811e8ec30c28f7725141295d0",
    "phase4_tree": "f2ca3080915aa68f403526b89dfc17454687aed6",
    "phase3_tag_object": "ac31524504b1b5cc63aabcfd5132a3eb4275e8e9",
    "phase3_commit": "e16e4b29b90f379615f1af97e47747cd1d531796",
    "phase3_tree": "a940f0d84a32adaf191f7ff2bebfb24cc855cde0",
    "phase2_commit": "01b1d7cba8c931fca95d041389cfb1902b7c89fe",
    "phase1_commit": "46c2f971e1a42cf49bd936bad94697b81bf31002",
    "public_fixture_rom_sha256":
        "272c94cdc79463cd1020ff14db1892ba56af07e4cfda97f5f1df89dd807772b9",
}

CLAIM_LEDGER = {
    "public_fixture_result": {
        "section": "legal public fixture result (bounded audited claim)",
        "proven": [
            {"claim": "Original Apache-2.0 NES fixture authored and built "
                      "deterministically (NROM-128, 16 KiB PRG, 8 KiB CHR, "
                      "vectors NMI $C196 / RESET $C000 / IRQ $C1F7, ROM SHA-256 "
                      "272c94cd...).",
             "evidence": "P5-01, P5-02"},
            {"claim": "Fail-closed iNES/NES 2.0 ingestion and full metadata "
                      "inventory for both selected fixtures.",
             "evidence": "P5-01"},
            {"claim": "Exact reachable frontier: 230 instructions / 508 bytes, "
                      "one dead padding NOP at $C0A7, zero reachable "
                      "undocumented opcodes.",
             "evidence": "P5-02"},
            {"claim": "CPU semantics: 181 differential vectors covering all 151 "
                      "official opcode forms plus flag/stack/branch/page-crossing/"
                      "wrap/BRK-RTI/2A03-decimal edges, zero mismatches.",
             "evidence": "P5-03"},
            {"claim": "Neutral architecture-neutral structure (231 instructions, "
                      "48 blocks, 11 functions, 11 translation units, 7 direct "
                      "call edges) with explicit reset/NMI/IRQ/BRK-continuation "
                      "roots and no fabricated boundaries or indirect targets.",
             "evidence": "P5-04"},
            {"claim": "Bounded NES CPU bus verified against the frozen "
                      "independent platform: RAM mirrors, all 8192 PPU window "
                      "addresses, APU/IO, controllers, OAM DMA, cartridge "
                      "mapping, fail-closed windows, 5000-operation mixed "
                      "differential.",
             "evidence": "P5-05"},
            {"claim": "Bounded PPU register/memory semantics verified against "
                      "the frozen independent PPU: 3000-step register script, "
                      "all 16384 PPU addresses, horizontal and vertical "
                      "mirroring, CHR-ROM write rejection.",
             "evidence": "P5-06"},
            {"claim": "Deterministic virtual timing/input/NMI scheduling with a "
                      "documented base-cost table covering all 151 official "
                      "opcodes and explicit vblank/NMI/IRQ semantics.",
             "evidence": "P5-07"},
            {"claim": "Deterministic native host emission for the fixture's "
                      "231 instructions through the typed runtime ABI, a "
                      "reproducible native build, and three identical native "
                      "runs.",
             "evidence": "P5-08"},
            {"claim": "Meaningful interactive behaviour on four declared "
                      "controller plans: exact guest transcripts, A-dependent "
                      "OAM/PPU observables, RIGHT-dependent RAM state, "
                      "input-independent nametable graphics.",
             "evidence": "P5-09"},
            {"claim": "Exact independent-reference equivalence on every "
                      "compared CPU/state field, all three digests, the full "
                      "frame transcript and exit state for all four plans, "
                      "with scheduling-tamper sensitivity.",
             "evidence": "P5-10"},
            {"claim": "Reproducible public package with a self-contained "
                      "rebuild from packaged generated sources reproducing the "
                      "canonical observable.",
             "evidence": "P5-12"},
        ],
        "bounded": [
            {"claim": "The claim is bounded to the audited public fixture, the "
                      "declared input plans and the bounded scheduling policy.",
             "evidence": "P5-08, P5-09, P5-10, P5-12"},
            {"claim": "Timing uses documented base instruction costs only; "
                      "page-cross and taken-branch penalties are not modelled.",
             "evidence": "P5-07"},
            {"claim": "The graphics observable is a bounded tile-space/PPU state "
                      "view submitted through the Phase-4 graphics boundary; it "
                      "is not rendered video output.",
             "evidence": "P5-06, P5-08"},
            {"claim": "Only NROM (mapper 0) is implemented for the public "
                      "fixture.",
             "evidence": "P5-05"},
        ],
    },
    "private_tmnt_observations": {
        "section": "private local compatibility fixture observations "
                   "(non-redistributed; no public claim)",
        "observations": [
            {"observation": "tmnt.nes: 262160 bytes, SHA-256 "
                            "2a9345e608ec0c57470dc6658ce8199ddea9c18076134d9ef2a56f91b0a066d1, "
                            "mapper 1 (MMC1/SxROM), 128 KiB PRG, 128 KiB CHR, "
                            "horizontal mirroring; execution status "
                            "BLOCKED_UNSUPPORTED_MAPPER.",
             "evidence": "P5-01, P5-11"},
            {"observation": "Frozen mapper and Phase-5 cartridge both fail "
                            "closed for mapper 1; no banking behaviour guessed.",
             "evidence": "P5-11"},
            {"observation": "Candidate SxROM fixed-bank frame (CANDIDATE / NOT "
                            "PROVEN): vectors NMI $C3A3, RESET $FFD8, IRQ "
                            "$C412; bounded candidate frontier 351 "
                            "instructions / 59 opcode forms; stop at 0xc570 "
                            "undocumented 0x7C; out-of-bank targets $864C and "
                            "$901E require an MMC1 PRG-bank model.",
             "evidence": "P5-11"},
            {"observation": "Private image bytes, banks and P5-11 evidence are "
                            "excluded from the public package by name and scan.",
             "evidence": "P5-11, P5-12"},
        ],
    },
    "general_nes": {
        "section": "general NES compatibility",
        "status": "NOT_PROVEN",
        "unproven": [
            {"area": "General NES game compatibility"},
            {"area": "Commercial-game compatibility"},
            {"area": "Cycle accuracy"},
            {"area": "Full PPU rendering and sprite timing accuracy"},
            {"area": "Full APU accuracy or audio equivalence"},
            {"area": "Arbitrary 6502 binary compatibility"},
            {"area": "Mapper-1 (MMC1) execution and TMNT compatibility"},
        ],
        "unsupported": [
            {"area": "Non-NROM mappers"},
            {"area": "NES 2.0 exponent/extended PRG/CHR size forms"},
            {"area": "Four-screen nametable arrangements"},
            {"area": "FDS/UNIF/UNF containers"},
        ],
        "not_tested": [
            {"area": "PAL/Dendy timing variants"},
            {"area": "Hardware IRQ delivery in the native path (the fixture "
                     "uses software BRK only)"},
            {"area": "CHR-RAM writes in the native path (the fixture uses CHR "
                     "ROM)"},
            {"area": "Sprite-0 hit and sprite overflow timing"},
            {"area": "Second controller port in the fixture"},
            {"area": "OAM decay and DMC/DPCM read conflicts"},
        ],
    },
}


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_ls_files(*patterns: str) -> set[str]:
    completed = subprocess.run(["git", "ls-files", "--", *patterns],
                               cwd=str(ROOT), capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
    return {line.strip() for line in completed.stdout.splitlines() if line.strip()}


def build_index() -> dict[str, Any]:
    tracked = git_ls_files(".openrecomp-phase5/evidence")
    files = []
    for stage in STAGES:
        directory = EVIDENCE_ROOT / stage
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(ROOT).as_posix()
            files.append({
                "stage": stage,
                "path": relative,
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
                "tracked": relative in tracked,
            })
    control = []
    for name in CONTROL_FILES:
        path = CONTROL / name
        control.append({
            "path": f".openrecomp-phase5/{name}",
            "size": path.stat().st_size,
            "sha256": sha256_file(path),
        })
    package = {
        "path": ".openrecomp-phase5/package/phase5_nes_package_v1.zip",
        "size": PACKAGE.stat().st_size if PACKAGE.is_file() else 0,
        "sha256": sha256_file(PACKAGE) if PACKAGE.is_file() else "",
    }
    manifest = []
    manifest_path = CONTROL / "SOURCE_SHA256SUMS.txt"
    for line in manifest_path.read_text(encoding="utf-8").strip().splitlines():
        digest, relative = line.split(" *", 1)
        manifest.append({"path": relative, "sha256": digest})
    return {
        "stage": "P5-91",
        "evidence_files": len(files),
        "stages": list(STAGES),
        "files": files,
        "control_plane": control,
        "package": package,
        "phase5_manifest": manifest,
        "boundaries": BOUNDARIES,
    }


def build_claim_record() -> dict[str, Any]:
    ledger = CLAIM_LEDGER
    record = {
        "stage": "P5-91",
        "vocabulary": ["PROVEN", "BOUNDED", "UNPROVEN", "UNSUPPORTED",
                       "NOT TESTED"],
        "ledger": ledger,
        "proven_count": len(ledger["public_fixture_result"]["proven"]),
        "bounded_count": len(ledger["public_fixture_result"]["bounded"]),
        "private_observation_count": len(
            ledger["private_tmnt_observations"]["observations"]),
        "unproven_count": len(ledger["general_nes"]["unproven"]),
        "unsupported_count": len(ledger["general_nes"]["unsupported"]),
        "not_tested_count": len(ledger["general_nes"]["not_tested"]),
        "generic_runtime_status": "NOT_PROVEN",
        "terminal_marker": "OPENRECOMP_PHASE5_NES_PLATFORM_PROOF=NOT_PROVEN",
        "compatibility_marker":
            "OPENRECOMP_PHASE5_GENERAL_NES_COMPATIBILITY=NOT_PROVEN",
        "sections": {
            "public": "legal public fixture result",
            "private": "private TMNT observations (non-redistributed)",
            "general": "general NES compatibility",
        },
    }
    return record


def canonical(document: Any) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


__all__ = [
    "BOUNDARIES",
    "CLAIM_LEDGER",
    "CONTROL_FILES",
    "STAGES",
    "build_claim_record",
    "build_index",
    "canonical",
]
