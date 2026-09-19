#!/usr/bin/env python3
"""Phase-6 evidence index and compatibility claim ledger (P6-91).

Builds the complete Phase-6 evidence index (every stage evidence file with
size/sha256/tracked status, control-plane hashes, frozen boundary identities,
manifest entries) and the claim ledger using the frozen vocabulary PROVEN /
BOUNDED / UNPROVEN / UNSUPPORTED / NOT TESTED, keeping four areas explicitly
separate:

1. the Phase-5 public NROM result (frozen legal public fixture proof);
2. the Phase-6 public MMC1 result (bounded audited public fixture proof);
3. the private local TMNT compatibility observation (non-redistributed, no
   public claim);
4. general NES compatibility (never promoted).

Every material limitation and the exact remaining TMNT blockers are recorded.
This module contains only metadata, hashes, addresses, counts and
classifications; it never reads or reproduces ROM bytes.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = ROOT / ".openrecomp-phase6" / "evidence"
CONTROL = ROOT / ".openrecomp-phase6"

STAGES = (tuple(f"P6-{index:02d}" for index in range(0, 14))
          + ("P6-90",))

CONTROL_FILES = (
    "CONTROL_POLICY.md", "EVIDENCE_SCHEMA.md", "FIXTURE_POLICY.md",
    "HANDOFF.md", "SCOPE.md", "SOURCE_SHA256SUMS.txt", "STAGE_QUEUE.md",
    "STATE.md",
)

BOUNDARIES = {
    "phase5_tag": "openrecomp-phase5-pass",
    "phase5_tag_object": "b5d6832ba2374b810f4c24500ed9093a9481fd8d",
    "phase5_commit": "e8d3627a622d0ca3196b117c5112f29fabdb49e7",
    "phase5_tree": "468fb9788350de393d3de2ca9471b7d874ee8dc9",
    "phase4_tag_object": "e7eaab18fee267b3d7962db13835c9e14dd77fc2",
    "phase4_commit": "b3c71fb690f00b4811e8ec30c28f7725141295d0",
    "phase4_tree": "f2ca3080915aa68f403526b89dfc17454687aed6",
    "phase3_tag_object": "ac31524504b1b5cc63aabcfd5132a3eb4275e8e9",
    "phase3_commit": "e16e4b29b90f379615f1af97e47747cd1d531796",
    "phase3_tree": "a940f0d84a32adaf191f7ff2bebfb24cc855cde0",
    "phase2_commit": "01b1d7cba8c931fca95d041389cfb1902b7c89fe",
    "phase1_commit": "46c2f971e1a42cf49bd936bad94697b81bf31002",
    "phase5_public_nrom_rom_sha256":
        "272c94cdc79463cd1020ff14db1892ba56af07e4cfda97f5f1df89dd807772b9",
    "phase6_public_mmc1_rom_sha256":
        "9e10dce532266592f9ccda781bc6d3a7354ab4951bd3db87e4f43d1c45056b70",
    "phase6_host_program_sha256":
        "6c1ccac5b49b6af231cef81115990c49d784edad5509615624078646866bf9f1",
    "phase6_support_sha256":
        "c15980d43ba9854c7e8dd5917a32a6e13ac3235d8fb7de06c50b91a2fb02ffb6",
    "phase6_executable_sha256":
        "0ba034bd1e7c081bb0ee07a8d8606ba425f1f0139db65eab9fb57c4ff30f6255",
    "private_image_sha256":
        "2a9345e608ec0c57470dc6658ce8199ddea9c18076134d9ef2a56f91b0a066d1",
    "private_image_size": 262160,
}

P5_91_CLAIM_RECORD_SHA256 = (
    "ef926dacb99315400a2631abbbaca909ccc794cec766deedd246bca9c4db2149")
P6_10_BLOCKERS_SHA256 = (
    "6b8b789cb691da742c270b81c98849bbda952642ad393cc5a4af230bc97e41c5")
P6_12_PIPELINE_REL = ".openrecomp-phase6/evidence/P6-12/workflow.json"
P6_13_FRONTIER_REL = ".openrecomp-phase6/evidence/P6-13/frontier_record.json"

CLAIM_LEDGER: dict[str, Any] = {
    "phase5_public_nrom": {
        "section": "Phase-5 public NROM result (legal public fixture, bounded "
                   "audited claim)",
        "status": "PROVEN",
        "evidence": "P5-01 .. P5-12, P5-90, P5-91, P5-99",
        "proven": [
            {"claim": "Original Apache-2.0 NROM-128 public fixture built "
                      "deterministically: 16 KiB PRG, 8 KiB CHR, ROM sha256 "
                      "272c94cd..., vectors NMI $C196 / RESET $C000 / IRQ "
                      "$C1F7.",
             "evidence": "P5-01, P5-02"},
            {"claim": "Exact reachable frontier: 230 instructions / 508 bytes, "
                      "one dead padding NOP at $C0A7, zero reachable "
                      "undocumented opcodes.",
             "evidence": "P5-02"},
            {"claim": "CPU semantics: 181 differential vectors over all 151 "
                      "official opcode forms plus flag/stack/branch/wrap/"
                      "BRK-RTI/2A03-decimal edges, zero mismatches.",
             "evidence": "P5-03"},
            {"claim": "Bounded NES CPU bus, PPU register/memory semantics, "
                      "timing/input/NMI scheduling verified against frozen "
                      "independent models.",
             "evidence": "P5-05, P5-06, P5-07"},
            {"claim": "Deterministic native emission and reproducible native "
                      "build; meaningful interactive behaviour over four "
                      "declared controller plans.",
             "evidence": "P5-08, P5-09"},
            {"claim": "Exact independent-reference equivalence on every "
                      "compared CPU/state field, digests, frame transcript and "
                      "exit state for all four plans.",
             "evidence": "P5-10"},
            {"claim": "Reproducible public package with a self-contained "
                      "rebuild reproducing the canonical observable.",
             "evidence": "P5-12"},
        ],
        "bounded": [
            {"claim": "Bounded to the audited public fixture, declared input "
                      "plans and the bounded scheduling policy.",
             "evidence": "P5-08 .. P5-10, P5-12"},
            {"claim": "Timing uses documented base instruction costs only; "
                      "page-cross and taken-branch penalties are not modelled.",
             "evidence": "P5-07"},
            {"claim": "The graphics observable is a bounded tile-space/PPU "
                      "state view, not rendered video output.",
             "evidence": "P5-06, P5-08"},
            {"claim": "Only NROM (mapper 0) is implemented on the Phase-5 "
                      "public path.",
             "evidence": "P5-05"},
        ],
    },
    "phase6_public_mmc1": {
        "section": "Phase-6 public MMC1 result (original Apache-2.0 MMC1 "
                   "fixture, bounded audited claim)",
        "status": "PROVEN",
        "evidence": "P6-01 .. P6-13, P6-90",
        "proven": [
            {"claim": "Supported MMC1 subset MMC1_SUBSET_V1 defined and "
                      "inventoried (four serial registers, 5-bit LSB-first "
                      "writes, reset bit, control/PRG/CHR modes, mirroring, "
                      "no PRG-RAM in the supported profile) with 26 pinned "
                      "requirement IDs and an explicit unsupported-variant "
                      "ledger V-001 .. V-012.",
             "evidence": "P6-01, P6-05"},
            {"claim": "Original Apache-2.0 public MMC1 proof fixture built "
                      "deterministically: 64 KiB PRG, 32 KiB CHR, ROM sha256 "
                      "9e10dce5..., vectors NMI $C1F8 / RESET $C000 / IRQ "
                      "$C235.",
             "evidence": "P6-06"},
            {"claim": "MMC1 serial protocol implemented and differentially "
                      "verified (4940+ comparisons, zero mismatches; all 256 "
                      "first-write classifications and 128 exhaustive commits).",
             "evidence": "P6-02"},
            {"claim": "MMC1 PRG banking implemented and differentially "
                      "verified (5120 register/bank combinations, 40960 "
                      "address mappings, zero mismatches).",
             "evidence": "P6-03"},
            {"claim": "MMC1 CHR banking and all four mirroring modes "
                      "implemented and differentially verified (1,013,760 CHR "
                      "mappings, 63,488 nametable comparisons, zero "
                      "mismatches).",
             "evidence": "P6-04"},
            {"claim": "Static recompilation of the proof fixture: 262 "
                      "reachable instructions / 571 bytes, neutral structure, "
                      "mapper service integration, deterministic emission "
                      "host program 6c1ccac5... / support c15980d4....",
             "evidence": "P6-07"},
            {"claim": "Native execution through the typed runtime ABI: "
                      "EXECUTABLE_REPRODUCIBLE build (executable 0ba034bd...), "
                      "three identical runs with bank switching, CPU, memory, "
                      "PPU, input and timing observables.",
             "evidence": "P6-08"},
            {"claim": "Exact independent MMC1 reference equivalence: all "
                      "three input plans match on CPU state, digests, mapper "
                      "registers/shift/writes, PRG/CHR banks, mirroring, frame "
                      "transcript, interrupt counts and exit state.",
             "evidence": "P6-09"},
            {"claim": "Evidence-driven platform expansion resolved as a "
                      "deterministic zero-delta decision: no platform addition "
                      "is justified by the observed evidence.",
             "evidence": "P6-11"},
            {"claim": "Reusable deterministic ROM-to-native workflow: full "
                      "public fixture path (inventory, classification, "
                      "frontier, translation, generated sources, reproducible "
                      "build, native execution) plus explicit fail-closed "
                      "classifications for unsupported container, mapper, "
                      "MMC1 variant, opcode, indirect control flow, bank state "
                      "and toolchain conditions; the source ROM is never "
                      "copied.",
             "evidence": "P6-12"},
            {"claim": "Whole regression: frozen Phase-1..5 chain re-verified "
                      "and every Phase-6 stage gate re-run with byte-identical "
                      "official output.",
             "evidence": "P6-90"},
        ],
        "bounded": [
            {"claim": "Bounded to the original Apache-2.0 MMC1 proof fixture, "
                      "the MMC1_SUBSET_V1 profile and the declared input plan "
                      "(00, 01, 80).",
             "evidence": "P6-06 .. P6-09, P6-12"},
            {"claim": "Translation requires a contiguous fully documented "
                      "fixed-bank ($C000-$FFFF) code region and the declared "
                      "$02FF page-wrap run-exit thunk; runtime-bank execution "
                      "in $8000-$BFFF is not translated.",
             "evidence": "P6-07, P6-12"},
            {"claim": "Timing uses documented base instruction costs; the "
                      "platform model is bounded and is not cycle-accurate.",
             "evidence": "P6-08, P6-09"},
            {"claim": "The graphics observable is bounded PPU/tile-space state "
                      "and digests, not rendered video output.",
             "evidence": "P6-08"},
            {"claim": "Only MMC1 variant V-001 (discrete, CHR ROM, no "
                      "PRG-RAM/battery) is supported.",
             "evidence": "P6-05"},
        ],
    },
    "private_tmnt_compatibility": {
        "section": "private local compatibility fixture observation "
                   "(non-redistributed; no public claim)",
        "status": "UNPROVEN",
        "fixture": "PRIVATE_LOCAL_COMPATIBILITY_FIXTURE",
        "source_path": r"D:\OpenRecomp\Roms\phase1\nes\primary\tmnt.nes",
        "image_sha256": BOUNDARIES["private_image_sha256"],
        "image_size": BOUNDARIES["private_image_size"],
        "observations": [
            {"observation": "iNES/NES 2.0 ingress classifies SUPPORTED_MMC1 "
                            "at the cartridge level: mapper 1/submapper 0, "
                            "horizontal mirroring, 8 x 16 KiB PRG, "
                            "16 x 8 KiB CHR, no PRG-RAM/battery/trainer; "
                            "power-on registers 0C 00 00 00, PRG windows "
                            "(0, 7), CHR mode 0, one-screen lower.",
             "evidence": "P6-10, P6-13"},
            {"observation": "Documented-control-flow walk fails closed at "
                            "0xC570 (undocumented opcode 0x7C after a jsr at "
                            "0xC56D); the bounded candidate traversal reaches "
                            "1250 instructions / 2711 bytes (202 fixed bank, "
                            "1048 power-on low window), 42 opcode forms, 11 "
                            "pending at the stop.",
             "evidence": "P6-10, P6-11, P6-12, P6-13"},
            {"observation": "Three unresolved indirect jumps through zero-page "
                            "pointer $E2 at 0x86E8, 0x8956 and 0x8F3C; runtime "
                            "targets are never guessed.",
             "evidence": "P6-10, P6-11, P6-12, P6-13"},
            {"observation": "Translation, generated sources, native build and "
                            "native execution are NOT_ATTEMPTED/NOT_GENERATED; "
                            "the MMC1 runtime support identity 2e3fa4ba... is "
                            "reproducible in memory without writing ROM-derived "
                            "source; native execution and interactive "
                            "behaviour are not reached.",
             "evidence": "P6-10, P6-13"},
        ],
        "exact_remaining_blockers": [
            {"classification": "unsupported_opcode",
             "detail": "documented-control-flow walk fails closed at 0xC570 "
                       "(undocumented 6502 opcode 0x7C) after a jsr at 0xC56D; "
                       "no private code/data boundary evidence is declared."},
            {"classification": "unresolved_indirect_control_flow",
             "detail": "unresolved jmp ($E2) sites at 0x86E8, 0x8956 and "
                       "0x8F3C; runtime jump-table targets must not be "
                       "guessed."},
            {"classification": "bank_state_unresolved",
             "detail": "1048 candidate instructions reach the mapper-switched "
                       "$8000-$BFFF window under the power-on PRG bank only; "
                       "runtime bank-state evidence is required to resolve the "
                       "actual bank sequence."},
            {"classification": "platform_runtime_not_tested",
             "detail": "PPU/APU/input/timing requirements beyond the bounded "
                       "Phase-5/6 platform model cannot be assessed until "
                       "translation completes."},
        ],
        "unproven": [
            {"area": "TMNT native execution and interactive playability"},
            {"area": "Any compatibility or correctness claim derived from the "
                     "private image"},
            {"area": "Runtime bank-state sequence of the private image"},
            {"area": "Private code/data boundaries and indirect jump tables"},
        ],
        "public_claim": "none; the private image and derived analysis never "
                        "enter public artifacts and no compatibility claim is "
                        "derived from it",
    },
    "general_nes": {
        "section": "general NES compatibility",
        "status": "UNPROVEN",
        "marker": "OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN",
        "unproven": [
            {"area": "General NES game compatibility"},
            {"area": "Commercial-game compatibility"},
            {"area": "All MMC1 boards, revisions and wiring variants"},
            {"area": "Cycle accuracy"},
            {"area": "Full PPU rendering and sprite timing accuracy"},
            {"area": "Full APU accuracy or audio equivalence"},
            {"area": "Arbitrary 6502 binary compatibility"},
            {"area": "Non-NROM/mapper-1 static-recompilation breadth"},
        ],
        "unsupported": [
            {"area": "Mappers other than mapper 0 (Phase-5 path) and the "
                     "supported mapper-1 subset"},
            {"area": "MMC1A/MMC1B/MMC1C revision differences"},
            {"area": "CHR-RAM MMC1 boards"},
            {"area": "PRG-RAM/battery MMC1 boards"},
            {"area": "SUROM/SOROM/SXROM and 512 KiB PRG wiring"},
            {"area": "Four-screen, VS UniSystem and PlayChoice layouts"},
            {"area": "Non-power-of-two PRG/CHR bank counts and non-zero "
                     "submapper variants"},
            {"area": "NES 2.0 exponent/extended PRG/CHR size forms"},
            {"area": "FDS/UNIF/UNF containers and console-derived assets"},
        ],
        "not_tested": [
            {"area": "PAL/Dendy timing variants"},
            {"area": "Hardware IRQ delivery in the native path"},
            {"area": "CHR-RAM writes in the native path"},
            {"area": "Sprite-0 hit and sprite overflow timing"},
            {"area": "Second controller port behaviour"},
            {"area": "OAM decay and DMC/DPCM read conflicts"},
            {"area": "MMC1 clone/FPGA implementations"},
            {"area": "Extended PPU/APU/input/timing requirements beyond the "
                     "bounded platform model"},
        ],
    },
}

LIMITATIONS = (
    "The Phase-6 proof is bounded to the original Apache-2.0 MMC1 fixture and "
    "the MMC1_SUBSET_V1 profile; it is not a general MMC1 or NES result.",
    "The private TMNT image is not playable; native execution is not reached "
    "and the same four blockers remain exactly as recorded at P6-10 .. P6-13.",
    "No MMC1 board variant beyond V-001 is supported or inferred.",
    "The workflow translates only a contiguous, fully documented fixed-bank "
    "region with the declared $02FF run-exit thunk.",
    "Timing is a documented base-cost model, not cycle accuracy; graphics and "
    "audio observables are bounded state views, not rendered media.",
    "The Phase-1 host gate set records two checks as SKIPPED_TOOLCHAIN_"
    "UNAVAILABLE (external POSIX/gcc toolchains).",
)


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_ls_files(*patterns: str) -> set[str]:
    completed = subprocess.run(["git", "ls-files", "--", *patterns],
                               cwd=str(ROOT), capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=300)
    return {line.strip() for line in completed.stdout.splitlines() if line.strip()}


def build_index() -> dict[str, Any]:
    tracked = git_ls_files(".openrecomp-phase6/evidence")
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
            "path": f".openrecomp-phase6/{name}",
            "size": path.stat().st_size,
            "sha256": sha256_file(path),
        })
    manifest = []
    manifest_path = CONTROL / "SOURCE_SHA256SUMS.txt"
    for line in manifest_path.read_text(encoding="utf-8").strip().splitlines():
        digest, relative = line.split(" *", 1)
        manifest.append({"path": relative, "sha256": digest})
    return {
        "stage": "P6-91",
        "evidence_files": len(files),
        "stages": list(STAGES),
        "files": files,
        "control_plane": control,
        "phase6_manifest": manifest,
        "boundaries": BOUNDARIES,
        "phase5_public_result": {
            "state": "PASS",
            "evidence": ".openrecomp-phase5/evidence/P5-99/",
            "claim_record_sha256": P5_91_CLAIM_RECORD_SHA256,
        },
        "private_observation_note":
            "the private fixture appears only as hashes/metadata/counts/"
            "addresses/classifications; no ROM bytes are indexed or copied",
    }


def build_claim_record() -> dict[str, Any]:
    ledger = CLAIM_LEDGER
    record = {
        "stage": "P6-91",
        "vocabulary": ["PROVEN", "BOUNDED", "UNPROVEN", "UNSUPPORTED",
                       "NOT TESTED"],
        "ledger": ledger,
        "phase5_proven_count": len(
            ledger["phase5_public_nrom"]["proven"]),
        "phase5_bounded_count": len(
            ledger["phase5_public_nrom"]["bounded"]),
        "proven_count": len(ledger["phase6_public_mmc1"]["proven"]),
        "bounded_count": len(ledger["phase6_public_mmc1"]["bounded"]),
        "private_observation_count": len(
            ledger["private_tmnt_compatibility"]["observations"]),
        "private_blocker_count": len(
            ledger["private_tmnt_compatibility"]["exact_remaining_blockers"]),
        "unproven_count": len(ledger["general_nes"]["unproven"]),
        "unsupported_count": len(ledger["general_nes"]["unsupported"]),
        "not_tested_count": len(ledger["general_nes"]["not_tested"]),
        "generic_runtime_status": "NOT_PROVEN",
        "terminal_marker": "OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=NOT_PROVEN",
        "compatibility_marker":
            "OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN",
        "sections": {
            "phase5_public_nrom": "Phase-5 public NROM result",
            "phase6_public_mmc1": "Phase-6 public MMC1 result",
            "private": "private TMNT compatibility observation "
                       "(non-redistributed)",
            "general": "general NES compatibility",
        },
        "limitations": list(LIMITATIONS),
    }
    return record


def canonical(document: Any) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True)
            + "\n").encode("utf-8")


__all__ = [
    "BOUNDARIES",
    "CLAIM_LEDGER",
    "CONTROL_FILES",
    "LIMITATIONS",
    "P5_91_CLAIM_RECORD_SHA256",
    "P6_10_BLOCKERS_SHA256",
    "P6_12_PIPELINE_REL",
    "P6_13_FRONTIER_REL",
    "STAGES",
    "build_claim_record",
    "build_index",
    "canonical",
]
