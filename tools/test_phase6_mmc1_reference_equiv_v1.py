#!/usr/bin/env python3
"""OpenRecomp Phase-6 independent MMC1 reference equivalence gate (P6-09).

Runs the same deterministic public MMC1 proof fixture and declared controller
plans through:

* the OpenRecomp-generated native result (host program emitted through the
  frozen Phase-5 CPU emitter plus the P6-07/P6-08 MMC1 runtime support built by
  the shared Phase-2 pipeline), and
* the independently structured P6-09 MMC1 reference path
  (`p6_reference_v1.run_reference`): the frozen independently written
  `ReferenceNES6502` oracle over an independent CPU bus/PPU/APU/timing model
  and the independently structured P6-02 .. P6-05 reference mapper models.

Compares CPU state, RAM/PPU/state digests, mapper state, PRG/CHR bank state,
mirroring, frame transcript, controller transcript, interrupt counts, the
runtime service transcript and the bounded final/exit state exactly, and
verifies the comparison is sensitive to schedule tampering and plan drift.

On success it emits::

    OPENRECOMP_P6_09=PASS
    OPENRECOMP_PHASE6_MMC1_REFERENCE_EQUIVALENCE_V1=PASS tests=<count>
    OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase6_mmc1_reference_equiv_v1.py \
        --evidence-dir .openrecomp-phase6/evidence/P6-09
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
PHASE6 = ROOT / ".openrecomp-phase6"
for entry in (str(PHASE6 / "src"), str(ROOT / ".openrecomp-phase5" / "src"),
              str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import p5_platform_v1 as platform  # noqa: E402
import p6_emit_v1 as emit  # noqa: E402
import p6_fixture_proof_v1 as proof_fixture  # noqa: E402
import p6_frontier_v1 as frontier  # noqa: E402
import p6_ines_v1 as ingestion  # noqa: E402
import p6_mapper1_chr_reference_v1 as chr_reference  # noqa: E402
import p6_private_fixture_v1 as private_fixture  # noqa: E402
import p6_reference_v1 as reference_module  # noqa: E402
from openrecomp.frontends import nes6502 as bridge  # noqa: E402

STAGE = "P6-09"
STAGE_MARKER = "OPENRECOMP_P6_09"
FEATURE_MARKER = "OPENRECOMP_PHASE6_MMC1_REFERENCE_EQUIVALENCE_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY"

PHASE5_TAG_OBJECT = "b5d6832ba2374b810f4c24500ed9093a9481fd8d"
PHASE5_COMMIT = "e8d3627a622d0ca3196b117c5112f29fabdb49e7"
PHASE5_TREE = "468fb9788350de393d3de2ca9471b7d874ee8dc9"

PROOF_ROM_SHA256 = "9e10dce532266592f9ccda781bc6d3a7354ab4951bd3db87e4f43d1c45056b70"
HOST_PROGRAM_SHA256 = "6c1ccac5b49b6af231cef81115990c49d784edad5509615624078646866bf9f1"
SUPPORT_SHA256 = "c15980d43ba9854c7e8dd5917a32a6e13ac3235d8fb7de06c50b91a2fb02ffb6"
EXIT_SITE = 0xC089
P6_08_INSTRUCTIONS = 262

INPUT_PLANS = {
    "p6_08": (0x00, 0x01, 0x80),
    "all_buttons": (0xFF, 0xFF, 0xFF),
    "mixed_bits": (0x00, 0x11, 0x22),
}

COMPARED_FIELDS = (
    "failed", "error", "exit", "steps", "pc", "a", "x", "y", "sp", "p",
    "frames", "nmi", "clock", "exit_arg", "ram_fnv1a64", "ppu_fnv1a64",
    "state_fnv1a64", "mmc1_regs", "mmc1_shift", "mmc1_count", "mmc1_writes",
    "prg_window_8000", "prg_window_c000", "chr_mode", "mirroring",
    "prg_ram_enabled",
)

P6_08_EXPECTED_FIELDS = {
    "failed": "0",
    "error": "",
    "exit": "1",
    "steps": "82731",
    "pc": "0xC089",
    "a": "0x5C",
    "x": "0x06",
    "y": "0x04",
    "sp": "0xFF",
    "p": "0x25",
    "frames": "9",
    "nmi": "6",
    "clock": "241746",
    "exit_arg": "0x0000C089",
    "ram_fnv1a64": "0x9B997E9AE6A788AD",
    "ppu_fnv1a64": "0xACDA2ECE461DE700",
    "state_fnv1a64": "0x0524F07A3A18DF2E",
    "mmc1_regs": "1F070703",
    "mmc1_shift": "0",
    "mmc1_count": "0",
    "mmc1_writes": "5905",
    "prg_window_8000": "3",
    "prg_window_c000": "3",
    "chr_mode": "1",
    "mirroring": "3",
    "prg_ram_enabled": "0",
    "exit_word": "0101010101010000",
}
P6_08_EXPECTED_FRAMES = [
    "frame[0]=00,C42A06F7E7A28E25,39E9FBAE5A7B29A5",
    "frame[1]=01,C42A06F7E7A28E25,39E9FBAE5A7B29A5",
    "frame[2]=80,C42A06F7E7A28E25,39E9FBAE5A7B29A5",
    "frame[3]=80,DF3335E91A6F6EA7,C2A1C3992E716B79",
    "frame[4]=80,DF3335E91A6F6EA7,4AA2162BF39CD093",
    "frame[5]=80,DF3335E91A6F6EA7,4AA2162BF39CD093",
    "frame[6]=80,448A23DEF7AAF934,ACDA2ECE461DE700",
    "frame[7]=80,448A23DEF7AAF934,ACDA2ECE461DE700",
    "frame[8]=80,448A23DEF7AAF934,ACDA2ECE461DE700",
]

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


def lf_normalize(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def write_json(name: str, document: Any) -> None:
    EVIDENCE_WRITES[name] = (json.dumps(document, indent=2, sort_keys=True)
                             + "\n").encode("utf-8")


def expect_fail(label: str, thunk) -> None:
    try:
        thunk()
    except reference_module.P6ReferenceError:
        check(f"reject:{label}", True)
        return
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(
            f"reject:{label}: raised {type(exc).__name__}: {exc}") from exc
    raise AssertionError(f"reject:{label}: accepted")


def run_regression(script: str, extra: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(ROOT / script), *extra], cwd=str(ROOT),
        capture_output=True)
    return {
        "script": script,
        "extra": extra,
        "returncode": completed.returncode,
        "stdout_bytes": len(completed.stdout),
        "stdout_sha256_raw": sha256_bytes(completed.stdout),
        "stdout_sha256_lf": sha256_bytes(lf_normalize(completed.stdout)),
        "stderr_bytes": len(completed.stderr),
        "stderr_empty": len(completed.stderr) == 0,
    }


def parse_observable(stdout: str) -> tuple[dict[str, str], list[str]]:
    fields: dict[str, str] = {}
    frames: list[str] = []
    for line in stdout.splitlines():
        if line.startswith("frame["):
            frames.append(line)
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            fields[key] = value
    return fields, frames


def native_run(rom: bytes, metadata: dict, instructions, plan: tuple[int, ...],
               name: str) -> dict[str, Any]:
    program = emit.emit_host_program(instructions, metadata)
    support = emit.emit_support(rom, metadata, plan)
    workspace = PHASE6 / "build" / "P6-09" / name
    if workspace.exists():
        shutil.rmtree(workspace)
    comparison = emit.build_native(program, support,
                                   fixture_id=f"p6-09-{name}",
                                   workspace=workspace)
    executable = workspace / "run1" / "program.exe"
    outputs = []
    stderrs: list[bytes] = []
    returncodes: list[int] = []
    for _index in range(2):
        completed = subprocess.run([str(executable)], capture_output=True,
                                   timeout=600)
        outputs.append(completed.stdout)
        stderrs.append(completed.stderr)
        returncodes.append(completed.returncode)
    fields, frames = parse_observable(outputs[0].decode("utf-8", "replace"))
    return {
        "classification": comparison.classification.name,
        "executable_reproducible": comparison.executable_reproducible,
        "host_program_sha256": sha256_bytes(program.encode("utf-8")),
        "support_sha256": sha256_bytes(support.encode("utf-8")),
        "executable_sha256": sha256_bytes(executable.read_bytes()),
        "returncodes": returncodes,
        "stderr_empty": all(not item for item in stderrs),
        "deterministic": len(set(outputs)) == 1,
        "outputs": outputs,
        "fields": fields,
        "frames": frames,
        "exit_word": fields.get("exit_word", ""),
    }


def compare(native: dict[str, Any], reference: dict[str, Any]) -> dict[str, Any]:
    mismatches = []
    for key in COMPARED_FIELDS:
        left = native["fields"].get(key)
        right = reference["fields"].get(key)
        if left != right:
            mismatches.append({"field": key, "native": left, "reference": right})
    if native["frames"] != reference["frames"]:
        mismatches.append({"field": "frames", "native": native["frames"],
                           "reference": reference["frames"]})
    if native["exit_word"] != reference.get("exit_word"):
        mismatches.append({"field": "exit_word", "native": native["exit_word"],
                           "reference": reference.get("exit_word")})
    return {"equivalent": not mismatches, "mismatches": mismatches}


def chr_layout_from_native(native_fields: dict[str, str],
                           chr_banks_8k: int) -> dict[str, Any]:
    registers = native_fields["mmc1_regs"]
    control = int(registers[0:2], 16)
    register_0 = int(registers[2:4], 16)
    register_1 = int(registers[4:6], 16)
    return chr_reference.reference_chr_banks(control, register_0, register_1,
                                             chr_banks_8k)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P6-09 independent MMC1 reference equivalence gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase6/evidence/P6-09")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}

    print("=== P6-09 Independent MMC1 Reference Equivalence Gate ===", flush=True)
    failure: str | None = None
    try:
        banner("source_integrity")
        manifest = PHASE6 / "SOURCE_SHA256SUMS.txt"
        check("source:manifest-exists", manifest.is_file())
        entries = []
        for line in manifest.read_text(encoding="utf-8").strip().splitlines():
            digest, rel = line.split(" *", 1)
            entries.append((digest, rel))
        bad = [rel for digest, rel in entries
               if not (ROOT / rel).is_file() or sha256_file(ROOT / rel) != digest]
        check("source:manifest-verified", bool(entries) and not bad)

        banner("frozen_chain")
        check("chain:phase5-tag-object",
              subprocess.run(["git", "rev-parse", "openrecomp-phase5-pass"],
                             cwd=str(ROOT), capture_output=True, text=True
                             ).stdout.strip() == PHASE5_TAG_OBJECT)
        check("chain:phase5-commit",
              subprocess.run(["git", "rev-parse", "openrecomp-phase5-pass^{commit}"],
                             cwd=str(ROOT), capture_output=True, text=True
                             ).stdout.strip() == PHASE5_COMMIT)
        check("chain:phase5-tree",
              subprocess.run(["git", "rev-parse", "openrecomp-phase5-pass^{tree}"],
                             cwd=str(ROOT), capture_output=True, text=True
                             ).stdout.strip() == PHASE5_TREE)
        check("chain:descends",
              subprocess.run(["git", "merge-base", "--is-ancestor", PHASE5_COMMIT,
                              "HEAD"], cwd=str(ROOT), capture_output=True
              ).returncode == 0)

        banner("control_plane")
        state = (PHASE6 / "STATE.md").read_text(encoding="utf-8")
        queue = (PHASE6 / "STAGE_QUEUE.md").read_text(encoding="utf-8")
        check("control-plane:stage-row", "| P6-09 |" in queue)
        check("control-plane:terminal-reserved",
              f"{TERMINAL_MARKER}=NOT_PROVEN" in queue)
        check("control-plane:compat-reserved",
              f"{COMPAT_MARKER}=NOT_PROVEN" in queue
              and f"{COMPAT_MARKER}=NOT_PROVEN" in state)

        banner("fixture")
        rom, metadata = proof_fixture.build_proof()
        check("fixture:proof-identity",
              metadata["rom_sha256"] == PROOF_ROM_SHA256
              and sha256_bytes(rom) == PROOF_ROM_SHA256)
        check("fixture:instruction-count",
              metadata["instruction_count"] == P6_08_INSTRUCTIONS
              and metadata["instructions_cross_checked"] == P6_08_INSTRUCTIONS)
        inventory = ingestion.ingest(rom, source_label="proof_fixture")
        phase6 = inventory["phase6"]
        check("fixture:supported-profile",
              phase6["status"] == "SUPPORTED_MMC1"
              and phase6["prg_banks_16k"] == 4
              and phase6["chr_banks_8k"] == 4
              and inventory["vectors"] == metadata["vectors"])
        image = frontier.build_mmc1_cpu_image(rom, metadata)
        region_start, region_end = frontier.code_region(metadata)
        instructions = bridge.bridge_region(image, entry=region_start,
                                            end=region_end)
        analysis = frontier.analysis(rom, metadata, inventory)
        indirect_sites = analysis["reachable"]["indirect_sites"]
        check("fixture:declared-exit-site",
              indirect_sites == [{"address": EXIT_SITE, "instruction": "jmp",
                                  "indirect": 0x02FF}]
              and reference_module.EXIT_SITE == EXIT_SITE)
        check("fixture:executed-region",
              region_start == 0xC000 and reference_module.GUEST_CODE_FLOOR == 0xC000)

        banner("schedule")
        used_words: dict[int, set[str]] = {}
        for instruction in instructions:
            word = (instruction.metadata or {}).get("adapter_fields", {}).get("word")
            used_words.setdefault(word, set()).add(instruction.op)
        schedule_mismatch = []
        for word in sorted(used_words):
            reference_cost = reference_module.REFERENCE_COSTS.get(word)
            audited_cost = platform.INSTRUCTION_COST.get(word)
            if reference_cost is None or reference_cost != audited_cost:
                schedule_mismatch.append({
                    "word": f"0x{word:02X}",
                    "reference": reference_cost,
                    "audited": audited_cost,
                })
        check("schedule:reference-costs-covered", not schedule_mismatch)
        check("schedule:table-matches-fixture",
              set(reference_module.REFERENCE_COSTS) == set(used_words))
        check("schedule:timing-constants",
              reference_module.FRAME_UNITS == platform.FRAME_CLOCK_UNITS
              and reference_module.VBLANK_UNITS == platform.VBLANK_CLOCK_UNITS
              and reference_module.NMI_ENTRY_COST == 7)
        FINDINGS["schedule"] = {
            "instruction_count": len(instructions),
            "opcode_forms": len(used_words),
            "words": {f"0x{word:02X}": sorted(names)
                      for word, names in sorted(used_words.items())},
            "mismatches": schedule_mismatch,
        }

        banner("equivalence")
        records: dict[str, Any] = {}
        for name, plan in INPUT_PLANS.items():
            native = native_run(rom, metadata, instructions, plan, name)
            check(f"{name}:native-reproducible",
                  native["classification"] == "EXECUTABLE_REPRODUCIBLE"
                  and native["executable_reproducible"] is True)
            check(f"{name}:native-runs",
                  native["returncodes"] == [0, 0] and native["stderr_empty"])
            check(f"{name}:native-deterministic", native["deterministic"])

            reference = reference_module.run_reference(rom, inventory, plan)
            reference_second = reference_module.run_reference(rom, inventory, plan)
            reference_deterministic = (
                reference["fields"] == reference_second["fields"]
                and reference["frames"] == reference_second["frames"]
                and reference["exit_word"] == reference_second["exit_word"]
                and reference["services"] == reference_second["services"])
            check(f"{name}:reference-deterministic", reference_deterministic)

            comparison = compare(native, reference)
            records[name] = {
                "plan": list(plan),
                "native": {key: native[key] for key in (
                    "classification", "executable_reproducible",
                    "host_program_sha256", "support_sha256",
                    "executable_sha256", "deterministic", "fields", "frames",
                    "exit_word")},
                "reference": {
                    "fields": reference["fields"],
                    "frames": reference["frames"],
                    "exit_word": reference["exit_word"],
                    "services": reference["services"],
                    "mapper": reference["mapper"],
                    "cpu": reference["cpu"],
                },
                "comparison": comparison,
            }
            check(f"{name}:equivalence", comparison["equivalent"])
            check(f"{name}:cpu-state",
                  native["fields"]["a"] == reference["fields"]["a"]
                  and native["fields"]["x"] == reference["fields"]["x"]
                  and native["fields"]["y"] == reference["fields"]["y"]
                  and native["fields"]["sp"] == reference["fields"]["sp"]
                  and native["fields"]["pc"] == reference["fields"]["pc"]
                  and native["fields"]["p"] == reference["fields"]["p"])
            check(f"{name}:memory-digests",
                  native["fields"]["ram_fnv1a64"] == reference["fields"]["ram_fnv1a64"]
                  and native["fields"]["ppu_fnv1a64"] == reference["fields"]["ppu_fnv1a64"]
                  and native["fields"]["state_fnv1a64"]
                  == reference["fields"]["state_fnv1a64"])
            check(f"{name}:mapper-state",
                  native["fields"]["mmc1_regs"] == reference["fields"]["mmc1_regs"]
                  and native["fields"]["mmc1_shift"] == reference["fields"]["mmc1_shift"]
                  and native["fields"]["mmc1_count"] == reference["fields"]["mmc1_count"]
                  and native["fields"]["mmc1_writes"] == reference["fields"]["mmc1_writes"])
            check(f"{name}:prg-banks",
                  native["fields"]["prg_window_8000"]
                  == reference["fields"]["prg_window_8000"]
                  and native["fields"]["prg_window_c000"]
                  == reference["fields"]["prg_window_c000"])
            expected_chr = chr_layout_from_native(native["fields"],
                                                  phase6["chr_banks_8k"])
            check(f"{name}:chr-banks",
                  native["fields"]["chr_mode"] == reference["fields"]["chr_mode"]
                  and expected_chr["bank_0"] == reference["mapper"]["chr_bank_0"]
                  and expected_chr["bank_1"] == reference["mapper"]["chr_bank_1"])
            check(f"{name}:mirroring",
                  native["fields"]["mirroring"] == reference["fields"]["mirroring"]
                  and native["fields"]["prg_ram_enabled"]
                  == reference["fields"]["prg_ram_enabled"])
            check(f"{name}:controller-transcript",
                  native["fields"]["exit_word"] == reference["exit_word"]
                  and [line.split("=", 1)[1].split(",")[0] for line in native["frames"]]
                  == [line.split("=", 1)[1].split(",")[0]
                      for line in reference["frames"]])
            check(f"{name}:interrupts",
                  native["fields"]["nmi"] == reference["fields"]["nmi"]
                  and native["fields"]["frames"] == reference["fields"]["frames"])
            check(f"{name}:services",
                  reference["services"] == [{"service": "p6.exit", "argc": 1,
                                             "args": [EXIT_SITE]}]
                  and native["fields"]["exit"] == "1"
                  and native["fields"]["exit_arg"] == reference["fields"]["exit_arg"])
            check(f"{name}:exit-state",
                  native["fields"]["failed"] == "0"
                  and native["fields"]["error"] == reference["fields"]["error"]
                  and native["fields"]["steps"] == reference["fields"]["steps"]
                  and native["fields"]["clock"] == reference["fields"]["clock"])

        check("p6_08:host-program-identity",
              all(records[name]["native"]["host_program_sha256"]
                  == HOST_PROGRAM_SHA256 for name in INPUT_PLANS))
        check("p6_08:support-identity",
              records["p6_08"]["native"]["support_sha256"] == SUPPORT_SHA256)
        check("p6_08:observables-pinned",
              all(records["p6_08"]["native"]["fields"].get(key) == value
                  for key, value in P6_08_EXPECTED_FIELDS.items()))
        check("p6_08:frames-pinned",
              records["p6_08"]["native"]["frames"] == P6_08_EXPECTED_FRAMES)
        check("p6_08:reference-observables-pinned",
              all(records["p6_08"]["reference"]["fields"].get(key) == value
                  for key, value in P6_08_EXPECTED_FIELDS.items()
                  if key != "exit_word")
              and records["p6_08"]["reference"]["exit_word"] == "0101010101010000")

        banner("sensitivity")
        cross = compare(records["p6_08"]["native"],
                        reference_module.run_reference(
                            rom, inventory, INPUT_PLANS["all_buttons"]))
        check("sensitivity:cross-plan", not cross["equivalent"])
        tampered_nmi = reference_module.run_reference(
            rom, inventory, INPUT_PLANS["p6_08"], nmi_entry_cost=9)
        check("sensitivity:nmi-entry-cost",
              tampered_nmi["fields"] != records["p6_08"]["reference"]["fields"])
        tampered_frame = reference_module.run_reference(
            rom, inventory, INPUT_PLANS["p6_08"],
            frame_units=reference_module.FRAME_UNITS + 1)
        check("sensitivity:frame-units",
              tampered_frame["fields"] != records["p6_08"]["reference"]["fields"])

        banner("negative")
        expect_fail("truncated-rom",
                    lambda: reference_module.run_reference(
                        rom[:-1], inventory, INPUT_PLANS["p6_08"]))
        expect_fail("unsupported-mapper",
                    lambda: reference_module.run_reference(
                        rom, dict(inventory, phase6=dict(
                            phase6, status="BLOCKED_UNSUPPORTED_MAPPER")),
                        INPUT_PLANS["p6_08"]))
        expect_fail("declared-battery",
                    lambda: reference_module.run_reference(
                        rom, dict(inventory, battery=True),
                        INPUT_PLANS["p6_08"]))
        expect_fail("declared-prg-ram",
                    lambda: reference_module.run_reference(
                        rom, dict(inventory, prg_ram_bytes=8192),
                        INPUT_PLANS["p6_08"]))
        expect_fail("empty-plan",
                    lambda: reference_module.run_reference(rom, inventory, ()))
        expect_fail("plan-value-range",
                    lambda: reference_module.run_reference(
                        rom, inventory, (0x100,)))
        fail_platform = reference_module.P6Mmc1ReferencePlatform(rom, inventory)
        expect_fail("prg-ram-window-read",
                    lambda: fail_platform.read_memory(0x6000))
        expect_fail("chr-rom-write",
                    lambda: fail_platform.ppu_memory_write(0x0000, 0x55))

        banner("regressions")
        regressions = []
        for script, extra in (
            ("tools/test_nes_rom_v1.py", []),
            ("tools/test_nes_platform_v1.py", []),
            ("tools/test_phase6_mmc1_serial_v1.py",
             ["--evidence-dir", ".openrecomp-phase6/scratch/P6-09/regression_p6_02"]),
            ("tools/test_phase6_mmc1_prg_v1.py",
             ["--evidence-dir", ".openrecomp-phase6/scratch/P6-09/regression_p6_03"]),
            ("tools/test_phase6_mmc1_chr_v1.py",
             ["--evidence-dir", ".openrecomp-phase6/scratch/P6-09/regression_p6_04"]),
            ("tools/test_phase6_mmc1_variant_v1.py",
             ["--evidence-dir", ".openrecomp-phase6/scratch/P6-09/regression_p6_05"]),
            ("tools/test_phase6_mmc1_inventory_v1.py",
             ["--evidence-dir", ".openrecomp-phase6/scratch/P6-09/regression_p6_01"]),
        ):
            record = run_regression(script, extra)
            check(f"regression:{script}:exit", record["returncode"] == 0)
            check(f"regression:{script}:stderr", record["stderr_empty"])
            regressions.append(record)
        FINDINGS["regressions"] = regressions

        banner("evidence_hygiene")
        write_json("equivalence.json", {
            "stage": STAGE,
            "fixture": {
                "rom_sha256": metadata["rom_sha256"],
                "instruction_count": metadata["instruction_count"],
                "exit_site": EXIT_SITE,
            },
            "plans": {name: list(plan) for name, plan in INPUT_PLANS.items()},
            "records": records,
        })
        write_json("sensitivity.json", {
            "stage": STAGE,
            "cross_plan_mismatches": cross["mismatches"],
            "tampered_nmi_cost_fields": tampered_nmi["fields"],
            "tampered_frame_units_fields": tampered_frame["fields"],
        })
        write_json("schedule.json", FINDINGS["schedule"])
        write_json("regressions.json", {"stage": STAGE, "regressions": regressions})
        private_bytes = private_fixture.PRIVATE_ROM.read_bytes()
        for name, data in EVIDENCE_WRITES.items():
            check(f"hygiene:no-public-rom-bytes:{name}", rom not in data)
            check(f"hygiene:no-private-rom-bytes:{name}", private_bytes not in data)
        FINDINGS["evidence_files"] = sorted(EVIDENCE_WRITES)
        FINDINGS["input_plans"] = {name: list(plan)
                                   for name, plan in INPUT_PLANS.items()}
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
    (EVIDENCE_DIR / "p6_09_tests.json").write_text(
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
