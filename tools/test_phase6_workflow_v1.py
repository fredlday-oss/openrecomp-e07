#!/usr/bin/env python3
"""OpenRecomp Phase-6 reusable ROM-to-native workflow gate (P6-12).

Exercises the frozen reusable workflow (`.openrecomp-phase6/src/p6_workflow_v1.py`)
against the original public MMC1 proof fixture end to end:

1. inventory and MMC1 subset/variant classification;
2. documented reachable frontier and bounded candidate traversal;
3. opcode/indirect-control-flow classification;
4. static recompilation of the contiguous fully documented region;
5. deterministic native host program + MMC1 runtime support sources;
6. reproducible native build through the shared Phase-2 pipeline;
7. deterministic native execution through the typed runtime ABI.

It also verifies fail-closed classification for an unsupported mapper, a
malformed image, an unsupported MMC1 variant and the private local image (whose
translation/control-flow blockers are recorded exactly), that the workflow
never copies the source ROM into its workspace, and that the CLI is
deterministic. The generated identities are anchored to the frozen P6-07/P6-08
records.

On success it emits::

    OPENRECOMP_P6_12=PASS
    OPENRECOMP_PHASE6_ROM_TO_NATIVE_WORKFLOW_V1=PASS tests=<count>
    OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase6_workflow_v1.py --evidence-dir .openrecomp-phase6/evidence/P6-12
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

import p6_fixture_proof_v1 as proof_fixture  # noqa: E402
import p6_private_fixture_v1 as private_fixture  # noqa: E402
import p6_workflow_v1 as workflow  # noqa: E402

STAGE = "P6-12"
STAGE_MARKER = "OPENRECOMP_P6_12"
FEATURE_MARKER = "OPENRECOMP_PHASE6_ROM_TO_NATIVE_WORKFLOW_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY"

PHASE5_TAG_OBJECT = "b5d6832ba2374b810f4c24500ed9093a9481fd8d"
PHASE5_COMMIT = "e8d3627a622d0ca3196b117c5112f29fabdb49e7"
PHASE5_TREE = "468fb9788350de393d3de2ca9471b7d874ee8dc9"

PROOF_ROM_SHA256 = "9e10dce532266592f9ccda781bc6d3a7354ab4951bd3db87e4f43d1c45056b70"
PROOF_ROM_SIZE = 98320
HOST_PROGRAM_SHA256 = "6c1ccac5b49b6af231cef81115990c49d784edad5509615624078646866bf9f1"
SUPPORT_SHA256 = "c15980d43ba9854c7e8dd5917a32a6e13ac3235d8fb7de06c50b91a2fb02ffb6"
EXECUTABLE_SHA256 = "0ba034bd1e7c081bb0ee07a8d8606ba425f1f0139db65eab9fb57c4ff30f6255"
INPUT_PLAN = (0x00, 0x01, 0x80)
CODE_REGION = [0xC000, 0xC23B]
REACHABLE_INSTRUCTIONS = 262
REACHABLE_BYTES = 571
DOCUMENTED_FORMS = 35
EXIT_SITE = {"address": 0xC089, "instruction": "jmp", "pointer": 0x02FF,
             "classification": "DECLARED_RUN_EXIT_SERVICE", "targets": []}

PRIVATE_PATH = r"D:\OpenRecomp\Roms\phase1\nes\primary\tmnt.nes"
PRIVATE_SHA256 = "2a9345e608ec0c57470dc6658ce8199ddea9c18076134d9ef2a56f91b0a066d1"
PRIVATE_SIZE = 262160
PRIVATE_STOP = {
    "address": 0xC570,
    "kind": "undocumented_opcode",
    "predecessor_address": 0xC56D,
    "predecessor_instruction": "jsr",
}
PRIVATE_CANDIDATE = {
    "instructions": 1250,
    "bytes": 2711,
    "low_window_instructions": 1048,
    "fixed_window_instructions": 202,
    "distinct_opcode_forms": 42,
    "pending_at_stop": 11,
}
PRIVATE_INDIRECT = [
    {"address": 0x86E8, "instruction": "jmp", "pointer": 0x00E2,
     "classification": "UNRESOLVED_INDIRECT_JUMP", "targets": []},
    {"address": 0x8956, "instruction": "jmp", "pointer": 0x00E2,
     "classification": "UNRESOLVED_INDIRECT_JUMP", "targets": []},
    {"address": 0x8F3C, "instruction": "jmp", "pointer": 0x00E2,
     "classification": "UNRESOLVED_INDIRECT_JUMP", "targets": []},
]

EXPECTED_FIELDS = {
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
EXPECTED_FRAMES = [
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

REGRESSIONS = (
    ("tools/test_nes_rom_v1.py", []),
    ("tools/test_nes_platform_v1.py", []),
    ("tools/test_phase6_mmc1_inventory_v1.py",
     ["--evidence-dir", ".openrecomp-phase6/scratch/P6-12/regression_p6_01"]),
    ("tools/test_phase6_mmc1_variant_v1.py",
     ["--evidence-dir", ".openrecomp-phase6/scratch/P6-12/regression_p6_05"]),
    ("tools/test_phase6_mmc1_reference_equiv_v1.py",
     ["--evidence-dir", ".openrecomp-phase6/scratch/P6-12/regression_p6_09"]),
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


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def lf_normalize(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def canonical(document: Any) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True)
            + "\n").encode("utf-8")


def write_json(name: str, document: Any) -> None:
    EVIDENCE_WRITES[name] = canonical(document)


def expect_workflow_fail(label: str, thunk) -> None:
    try:
        thunk()
    except workflow.P6WorkflowError:
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
    markers = [line for line in
               completed.stdout.decode("utf-8", errors="replace").splitlines()
               if line.startswith("OPENRECOMP_")]
    return {
        "script": script,
        "extra": extra,
        "returncode": completed.returncode,
        "stdout_bytes": len(completed.stdout),
        "stdout_sha256_raw": sha256_bytes(completed.stdout),
        "stdout_sha256_lf": sha256_bytes(lf_normalize(completed.stdout)),
        "stderr_bytes": len(completed.stderr),
        "stderr_empty": len(completed.stderr) == 0,
        "markers": markers,
    }


def write_probe_rom(directory: pathlib.Path, name: str,
                    data: bytes) -> pathlib.Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_bytes(data)
    return path


def workspace_rom_copies(workspace: pathlib.Path,
                         digest: str) -> list[str]:
    matches: list[str] = []
    if not workspace.is_dir():
        return matches
    for path in sorted(workspace.rglob("*")):
        if not path.is_file():
            continue
        if sha256_file(path) == digest:
            matches.append(path.relative_to(workspace).as_posix())
    return matches


def remove_probe_roms(scratch: pathlib.Path) -> None:
    for name in ("input", "probes"):
        target = scratch / name
        if target.is_dir():
            shutil.rmtree(target)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P6-12 reusable ROM-to-native workflow gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase6/evidence/P6-12")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}
    scratch = ROOT / ".openrecomp-phase6" / "scratch" / "P6-12"
    input_dir = scratch / "input"
    workspace_dir = scratch / "workspace"
    remove_probe_roms(scratch)

    print("=== P6-12 Reusable ROM-to-Native Workflow Gate ===", flush=True)
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
        check("control-plane:stage-row", "| P6-12 |" in queue)
        check("control-plane:terminal-reserved",
              f"{TERMINAL_MARKER}=NOT_PROVEN" in queue)
        check("control-plane:compat-reserved",
              f"{COMPAT_MARKER}=NOT_PROVEN" in queue
              and f"{COMPAT_MARKER}=NOT_PROVEN" in state)

        banner("workflow_public_fixture")
        rom, metadata = proof_fixture.build_proof()
        check("fixture:proof-identity",
              metadata["rom_sha256"] == PROOF_ROM_SHA256
              and len(rom) == PROOF_ROM_SIZE)
        rom_path = write_probe_rom(input_dir, "p6_public_mmc1_proof.nes", rom)
        if workspace_dir.exists():
            shutil.rmtree(workspace_dir)
        report_a = workflow.run(rom_path, plan=INPUT_PLAN,
                                workspace=workspace_dir, build=True)
        report_b = workflow.run(rom_path, plan=INPUT_PLAN, build=True)
        report_c = workflow.run(rom_path, plan=INPUT_PLAN, build=False)
        report_d = workflow.run(rom_path, plan=INPUT_PLAN, build=False)
        check("workflow:deterministic-full",
              canonical(report_a) == canonical(report_b))
        check("workflow:deterministic-analysis",
              canonical(report_c) == canonical(report_d))
        check("workflow:status", report_a["status"] == "COMPLETED"
              and report_a["blockers"] == []
              and report_a["stop_reason"] == "native execution reached")
        check("workflow:input-classification",
              report_a["input"]["source_classification"]
              == "LOCAL_USER_SUPPLIED_ROM"
              and report_a["input"]["source_rom_copied"] is False
              and report_a["input"]["image_sha256"] == PROOF_ROM_SHA256
              and report_a["input"]["image_size"] == PROOF_ROM_SIZE)
        check("workflow:inventory",
              report_a["inventory"]["status"] == "OK"
              and report_a["inventory"]["container"] == "ines"
              and report_a["inventory"]["mapper"] == 1
              and report_a["inventory"]["prg_bytes"] == 0x10000
              and report_a["inventory"]["chr_bytes"] == 0x8000)
        check("workflow:mapper-platform",
              report_a["mapper_platform"]["status"] == "SUPPORTED_MMC1"
              and report_a["mapper_platform"]["variant"]["status"]
              == "SUPPORTED_PROFILE"
              and report_a["mapper_platform"]["cartridge"]["status"]
              == "SUPPORTED_MMC1")
        check("workflow:power-on-state",
              report_a["mapper_platform"]["cartridge"]["power_on_registers"]
              == {"control": 0x0C, "chr_bank_0": 0, "chr_bank_1": 0,
                  "prg_bank": 0}
              and report_a["mapper_platform"]["cartridge"]
              ["power_on_prg_window"] == [0, 3]
              and report_a["mapper_platform"]["cartridge"]
              ["power_on_chr_mode"] == 0
              and report_a["mapper_platform"]["cartridge"]
              ["power_on_mirroring"] == "one_screen_lower"
              and report_a["mapper_platform"]["cartridge"]
              ["prg_ram_enabled"] is False)

        banner("workflow_frontier")
        check("frontier:documented",
              report_a["frontier"]["documented_status"] == "OK"
              and report_a["frontier"]["documented_error"] == "")
        check("frontier:region",
              report_a["frontier"]["code_region"] == CODE_REGION
              and report_a["frontier"]["contiguous"] is True
              and report_a["frontier"]["low_window_reachable"] == [])
        check("frontier:candidate",
              report_a["frontier"]["candidate"]["instructions"]
              == REACHABLE_INSTRUCTIONS
              and report_a["frontier"]["candidate"]["bytes"] == REACHABLE_BYTES
              and report_a["frontier"]["candidate"]["low_window_instructions"] == 0
              and report_a["frontier"]["candidate"]["fixed_window_instructions"]
              == REACHABLE_INSTRUCTIONS
              and report_a["frontier"]["candidate"]["truncated"] is False)
        check("opcode:supported",
              report_a["opcode_frontier"]["status"] == "SUPPORTED"
              and report_a["opcode_frontier"]["documented_forms"]
              == DOCUMENTED_FORMS
              and report_a["opcode_frontier"]["reachable_instructions"]
              == REACHABLE_INSTRUCTIONS
              and report_a["opcode_frontier"]["reachable_bytes"]
              == REACHABLE_BYTES
              and report_a["opcode_frontier"]["unsupported"] == [])
        check("indirect:declared-run-exit",
              report_a["indirect_control_flow"]["status"] == "RESOLVED"
              and report_a["indirect_control_flow"]["sites"] == [EXIT_SITE])
        check("translation:translated",
              report_a["translation"]["status"] == "TRANSLATED"
              and report_a["translation"]["region"] == CODE_REGION
              and report_a["translation"]["instructions"]
              == REACHABLE_INSTRUCTIONS
              and report_a["translation"]["indirect_exit_service"] == "p6.exit")

        banner("generated_sources")
        generated = report_a["generated_sources"]
        check("generated:status", generated["status"] == "GENERATED")
        check("generated:host-identity",
              generated["host_program_sha256"] == HOST_PROGRAM_SHA256)
        check("generated:support-identity",
              generated["support_sha256"] == SUPPORT_SHA256)
        check("generated:plan", generated["input_plan"] == list(INPUT_PLAN))
        check("generated:written",
              generated["written"] == ["generated/generated.c",
                                       "generated/p6_nes_support.c"])
        host_file = workspace_dir / "generated" / "generated.c"
        support_file = workspace_dir / "generated" / "p6_nes_support.c"
        check("generated:host-file",
              host_file.is_file()
              and sha256_file(host_file) == HOST_PROGRAM_SHA256)
        check("generated:support-file",
              support_file.is_file()
              and sha256_file(support_file) == SUPPORT_SHA256)

        banner("native_build")
        native_build = report_a["native_build"]
        check("build:status",
              native_build["status"] == "BUILT"
              and native_build["classification"] == "EXECUTABLE_REPRODUCIBLE"
              and native_build["executable_reproducible"] is True
              and native_build["manifest_reproducible"] is True)
        check("build:executable-identity",
              native_build["executable_sha256"] == EXECUTABLE_SHA256)
        check("build:toolchain",
              native_build["toolchain"] == {"compiler": "clang-cl.exe",
                                            "linker": "lld-link.exe"}
              and native_build["runs"] == 2)

        banner("native_execution")
        execution = report_a["native_execution"]
        check("execution:status",
              execution["status"] == "EXECUTED" and execution["runs"] == 3)
        check("execution:no-guest-on-host",
              execution["guest_code_executed_on_host"] is False)
        for key, value in EXPECTED_FIELDS.items():
            check(f"observable:{key}", execution["fields"].get(key) == value)
        check("observable:frames-transcript",
              execution["frames"] == EXPECTED_FRAMES)
        check("platform:model-active",
              report_a["platform_runtime"]["status"]
              == "BOUNDED_NES_PLATFORM_MODEL_ACTIVE")

        banner("record_anchors")
        p6_07 = json.loads(
            (PHASE6 / "evidence" / "P6-07" / "emission.json").read_text(
                encoding="utf-8"))
        p6_08 = json.loads(
            (PHASE6 / "evidence" / "P6-08" / "build.json").read_text(
                encoding="utf-8"))
        p6_08_exec = json.loads(
            (PHASE6 / "evidence" / "P6-08" / "executions.json").read_text(
                encoding="utf-8"))
        check("anchor:p6-07-host-program",
              p6_07["host_program_sha256"] == HOST_PROGRAM_SHA256
              and generated["host_program_sha256"]
              == p6_07["host_program_sha256"])
        check("anchor:p6-07-support",
              p6_07["support_sha256"] == SUPPORT_SHA256
              and generated["support_sha256"] == p6_07["support_sha256"])
        check("anchor:p6-08-executable",
              p6_08["executable_sha256"] == EXECUTABLE_SHA256
              and native_build["executable_sha256"]
              == p6_08["executable_sha256"])
        check("anchor:p6-08-observables",
              p6_08_exec["fields"] == execution["fields"]
              and p6_08_exec["frames"] == execution["frames"])

        banner("determinism_hygiene")
        check("hygiene:no-rom-copy-in-workspace",
              workspace_rom_copies(workspace_dir, PROOF_ROM_SHA256) == [])
        check("hygiene:no-rom-extension-in-workspace",
              [path.name for path in workspace_dir.rglob("*.nes")] == [])
        cli = [sys.executable,
               str(PHASE6 / "src" / "p6_workflow_v1.py"),
               "--rom", str(rom_path), "--no-build", "--json"]
        cli_runs = [subprocess.run(cli, cwd=str(ROOT), capture_output=True)
                    for _index in range(2)]
        check("cli:exit-zero",
              all(completed.returncode == 0 for completed in cli_runs))
        check("cli:stderr-empty",
              all(completed.stderr == b"" for completed in cli_runs))
        check("cli:stdout-identical",
              cli_runs[0].stdout == cli_runs[1].stdout)
        check("cli:report-equivalent",
              lf_normalize(cli_runs[0].stdout) == canonical(report_c))

        banner("negative_classification")
        probe_dir = scratch / "probes"
        mapper2 = bytearray(rom)
        mapper2[6] = 0x20
        mapper2_path = write_probe_rom(probe_dir, "mapper2.nes", bytes(mapper2))
        mapper2_report = workflow.run(mapper2_path, build=False)
        check("negative:mapper2",
              mapper2_report["status"] == "FAIL_CLOSED"
              and mapper2_report["mapper_platform"]["status"]
              == "BLOCKED_UNSUPPORTED_MAPPER"
              and len(mapper2_report["blockers"]) == 1
              and mapper2_report["blockers"][0]["code"]
              == "BLOCKED_UNSUPPORTED_MAPPER"
              and mapper2_report["blockers"][0]["stage"] == "mapper_platform"
              and mapper2_report["blockers"][0]["classification"]
              == "unsupported_mapper"
              and "mapper 2" in mapper2_report["blockers"][0]["detail"])
        check("negative:mapper2-not-attempted",
              mapper2_report["translation"]["status"] == "NOT_ATTEMPTED"
              and mapper2_report["native_build"]["status"] == "NOT_ATTEMPTED"
              and mapper2_report["native_execution"]["status"] == "NOT_ATTEMPTED")
        malformed_path = write_probe_rom(probe_dir, "truncated.nes",
                                         b"NES\x1a" + bytes(10))
        malformed = workflow.run(malformed_path, build=False)
        check("negative:malformed",
              malformed["status"] == "FAIL_CLOSED"
              and malformed["inventory"]["status"] == "REJECTED"
              and malformed["blockers"][0]["code"]
              == "BLOCKED_UNSUPPORTED_CONTAINER"
              and malformed["blockers"][0]["classification"]
              == "unsupported_container")
        battery = bytearray(rom)
        battery[6] = 0x12
        battery_path = write_probe_rom(probe_dir, "battery.nes", bytes(battery))
        battery_report = workflow.run(battery_path, build=False)
        check("negative:battery-variant",
              battery_report["status"] == "FAIL_CLOSED"
              and battery_report["mapper_platform"]["status"]
              == "BLOCKED_UNSUPPORTED_MMC1_VARIANT"
              and battery_report["blockers"][0]["classification"]
              == "unsupported_mmc1_variant"
              and "battery_or_prg_ram"
              in battery_report["blockers"][0]["detail"])

        banner("negative_private")
        private_report = workflow.run(private_fixture.PRIVATE_ROM, build=False)
        check("private:identity",
              private_report["input"]["source_classification"]
              == "PRIVATE_LOCAL_COMPATIBILITY_FIXTURE"
              and private_report["input"]["image_sha256"] == PRIVATE_SHA256
              and private_report["input"]["image_size"] == PRIVATE_SIZE
              and private_report["input"]["source_rom_copied"] is False)
        check("private:supported-mmc1",
              private_report["mapper_platform"]["status"] == "SUPPORTED_MMC1"
              and private_report["mapper_platform"]["variant"]["status"]
              == "SUPPORTED_PROFILE")
        candidate = private_report["frontier"]["candidate"]
        stop = candidate["stop"] or {}
        check("private:opcode-frontier",
              private_report["frontier"]["documented_status"] == "FAIL_CLOSED"
              and private_report["opcode_frontier"]["status"]
              == "BLOCKED_UNSUPPORTED_OPCODE"
              and stop.get("address") == PRIVATE_STOP["address"]
              and stop.get("kind") == PRIVATE_STOP["kind"]
              and stop.get("predecessor", {}).get("address")
              == PRIVATE_STOP["predecessor_address"]
              and stop.get("predecessor", {}).get("instruction")
              == PRIVATE_STOP["predecessor_instruction"])
        check("private:candidate-counts",
              all(candidate[key] == value
                  for key, value in PRIVATE_CANDIDATE.items()))
        check("private:indirect-frontier",
              private_report["indirect_control_flow"]["status"] == "UNRESOLVED"
              and private_report["indirect_control_flow"]["sites"]
              == PRIVATE_INDIRECT)
        check("private:translation-blocked",
              private_report["translation"]["status"] == "NOT_ATTEMPTED"
              and private_report["generated_sources"]["status"]
              == "NOT_GENERATED"
              and private_report["native_build"]["status"] == "NOT_ATTEMPTED"
              and private_report["native_execution"]["status"]
              == "NOT_ATTEMPTED")
        check("private:platform-not-tested",
              private_report["platform_runtime"]["status"] == "NOT_TESTED")
        check("private:blocker-classes",
              [item["classification"] for item in private_report["blockers"]]
              == ["unsupported_opcode", "unresolved_indirect_control_flow",
                  "bank_state_unresolved", "platform_runtime_not_tested"])
        check("private:public-claim-none",
              private_report["public_claim"].startswith("none"))

        banner("negative_invocation")
        expect_workflow_fail(
            "missing-path",
            lambda: workflow.run(pathlib.Path(
                r"D:\OpenRecomp\Roms\phase1\nes\primary\absent.nes")))
        expect_workflow_fail("empty-plan", lambda: workflow.run(rom_path, plan=()))
        expect_workflow_fail("plan-value-range",
                             lambda: workflow.run(rom_path, plan=(0x100,)))
        expect_workflow_fail("budget-range",
                             lambda: workflow.run(rom_path, budget=0))
        expect_workflow_fail("run-count-range",
                             lambda: workflow.run(rom_path, run_count=-1))

        remove_probe_roms(scratch)

        banner("regressions")
        regressions = []
        for script, extra in REGRESSIONS:
            record = run_regression(script, extra)
            check(f"regression:{script}:exit", record["returncode"] == 0)
            check(f"regression:{script}:stderr", record["stderr_empty"])
            regressions.append(record)
        check("regression:p6-09-reference-equivalence-marker",
              any("OPENRECOMP_PHASE6_MMC1_REFERENCE_EQUIVALENCE_V1=PASS"
                  in marker for marker in regressions[-1]["markers"]))
        FINDINGS["regressions"] = regressions

        banner("evidence_hygiene")
        write_json("workflow.json", {
            "stage": STAGE,
            "workflow": workflow.WORKFLOW_ID,
            "public_report": report_a,
        })
        write_json("blockers.json", {
            "stage": STAGE,
            "unsupported_mapper": mapper2_report["blockers"],
            "malformed": malformed["blockers"],
            "unsupported_variant": battery_report["blockers"],
            "private_image": private_report["blockers"],
            "private_stop_reason": private_report["stop_reason"],
        })
        write_json("anchors.json", {
            "stage": STAGE,
            "host_program_sha256": HOST_PROGRAM_SHA256,
            "support_sha256": SUPPORT_SHA256,
            "executable_sha256": EXECUTABLE_SHA256,
            "code_region": CODE_REGION,
            "input_plan": list(INPUT_PLAN),
            "p6_07_host_program_sha256": p6_07["host_program_sha256"],
            "p6_07_support_sha256": p6_07["support_sha256"],
            "p6_08_executable_sha256": p6_08["executable_sha256"],
        })
        write_json("regressions.json", {"stage": STAGE, "regressions": regressions})
        private_bytes = private_fixture.PRIVATE_ROM.read_bytes()
        for name, data in EVIDENCE_WRITES.items():
            check(f"hygiene:no-public-rom-bytes:{name}", rom not in data)
            check(f"hygiene:no-private-rom-bytes:{name}", private_bytes not in data)
        FINDINGS["evidence_files"] = sorted(EVIDENCE_WRITES)
    except Exception as exc:  # noqa: BLE001 - fail closed without traceback
        failure = f"{type(exc).__name__}: {exc}"
    finally:
        remove_probe_roms(scratch)

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
    (EVIDENCE_DIR / "p6_12_tests.json").write_text(
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
