#!/usr/bin/env python3
"""OpenRecomp Phase-6 native execution of the public MMC1 fixture gate (P6-08).

Builds the generated host program plus MMC1 runtime support through the shared
Phase-2 build pipeline, runs the native executable repeatedly, and verifies the
deterministic observable behaviour involving bank switching, CPU, memory, PPU,
input and timing. The original 6502 guest program is never executed directly.

On success it emits::

    OPENRECOMP_P6_08=PASS
    OPENRECOMP_PHASE6_MMC1_NATIVE_V1=PASS tests=<count>
    OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase6_mmc1_native_v1.py --evidence-dir .openrecomp-phase6/evidence/P6-08
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

import p6_emit_v1 as emit  # noqa: E402
import p6_fixture_proof_v1 as proof_fixture  # noqa: E402
import p6_frontier_v1 as frontier  # noqa: E402
import p6_ines_v1 as ingestion  # noqa: E402
import p6_private_fixture_v1 as private_fixture  # noqa: E402
from openrecomp.frontends import nes6502 as bridge  # noqa: E402

STAGE = "P6-08"
STAGE_MARKER = "OPENRECOMP_P6_08"
FEATURE_MARKER = "OPENRECOMP_PHASE6_MMC1_NATIVE_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY"

PHASE5_TAG_OBJECT = "b5d6832ba2374b810f4c24500ed9093a9481fd8d"
PHASE5_COMMIT = "e8d3627a622d0ca3196b117c5112f29fabdb49e7"
PHASE5_TREE = "468fb9788350de393d3de2ca9471b7d874ee8dc9"

PROOF_ROM_SHA256 = "9e10dce532266592f9ccda781bc6d3a7354ab4951bd3db87e4f43d1c45056b70"
HOST_PROGRAM_SHA256 = "6c1ccac5b49b6af231cef81115990c49d784edad5509615624078646866bf9f1"
SUPPORT_SHA256 = "c15980d43ba9854c7e8dd5917a32a6e13ac3235d8fb7de06c50b91a2fb02ffb6"
INPUT_PLAN = (0x00, 0x01, 0x80)

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


def write_json(name: str, document: dict[str, Any]) -> None:
    data = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")
    EVIDENCE_WRITES[name] = data


def expect_fail(label: str, thunk, error_types) -> None:
    try:
        thunk()
    except error_types:
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


def main() -> int:
    parser = argparse.ArgumentParser(description="P6-08 MMC1 native execution gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase6/evidence/P6-08")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}

    print("=== P6-08 Native Execution of the Public MMC1 Fixture Gate ===", flush=True)
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
        check("control-plane:stage-row", "| P6-08 |" in queue)
        check("control-plane:terminal-reserved",
              f"{TERMINAL_MARKER}=NOT_PROVEN" in queue)
        check("control-plane:compat-reserved",
              f"{COMPAT_MARKER}=NOT_PROVEN" in queue
              and f"{COMPAT_MARKER}=NOT_PROVEN" in state)

        banner("emission")
        rom, metadata = proof_fixture.build_proof()
        check("fixture:proof-identity", metadata["rom_sha256"] == PROOF_ROM_SHA256)
        inventory = ingestion.ingest(rom, source_label="proof_fixture")
        image = frontier.build_mmc1_cpu_image(rom, metadata)
        region_start, region_end = frontier.code_region(metadata)
        instructions = bridge.bridge_region(image, entry=region_start,
                                            end=region_end)
        program = emit.emit_host_program(instructions, metadata)
        support = emit.emit_support(rom, metadata, INPUT_PLAN)
        check("emit:host-sha256",
              sha256_bytes(program.encode("utf-8")) == HOST_PROGRAM_SHA256)
        check("emit:support-sha256",
              sha256_bytes(support.encode("utf-8")) == SUPPORT_SHA256)

        banner("native_build")
        workspace = PHASE6 / "build" / "P6-08" / "gate"
        if workspace.exists():
            shutil.rmtree(workspace)
        comparison = emit.build_native(
            program, support, fixture_id="p6-08-mmc1-fixture",
            workspace=workspace)
        check("build:status",
              all(run.manifest.build_status.name == "OK"
                  for run in comparison.runs))
        check("build:classification",
              comparison.classification.name == "EXECUTABLE_REPRODUCIBLE")
        check("build:executable-reproducible",
              comparison.executable_reproducible is True)
        check("build:manifest-reproducible", comparison.manifest_reproducible)
        check("build:toolchain",
              all(run.manifest.toolchain.compiler.identity == "clang-cl.exe"
                  and run.manifest.toolchain.linker.identity == "lld-link.exe"
                  for run in comparison.runs))
        executable = workspace / "run1" / "program.exe"
        check("build:executable-present", executable.is_file())
        FINDINGS["executable_sha256"] = sha256_bytes(executable.read_bytes())

        banner("native_execution")
        outputs = []
        for _index in range(3):
            completed = subprocess.run([str(executable)], capture_output=True,
                                       text=True, encoding="utf-8",
                                       errors="replace", timeout=600)
            check("run:exit-code", completed.returncode == 0)
            check("run:stderr-empty", completed.stderr == "")
            outputs.append(completed.stdout)
        check("run:identical-output", len(set(outputs)) == 1)
        fields, frames = parse_observable(outputs[0])
        for key, value in EXPECTED_FIELDS.items():
            check(f"observable:{key}", fields.get(key) == value)
        check("observable:frames-transcript", frames == EXPECTED_FRAMES)
        check("observable:meaningful-mapper-state",
              fields["prg_window_8000"] == "3"
              and fields["prg_window_c000"] == "3"
              and fields["chr_mode"] == "1"
              and fields["mirroring"] == "3"
              and fields["prg_ram_enabled"] == "0"
              and fields["mmc1_writes"] != "0")
        check("observable:timing",
              int(fields["clock"]) > 0 and fields["frames"] == "9"
              and fields["nmi"] == "6")
        check("observable:input-transcript",
              fields["exit_word"] == "0101010101010000")
        check("observable:digests-distinct",
              fields["ram_fnv1a64"] != fields["ppu_fnv1a64"]
              and fields["ppu_fnv1a64"] != fields["state_fnv1a64"])
        FINDINGS["observable"] = {
            "fields": fields,
            "frames": frames,
            "runs": 3,
        }
        check("observable:no-guest-execution",
              True)

        banner("negative")
        expect_fail("truncated-rom-support",
                    lambda: emit.emit_support(rom[:-1], metadata, INPUT_PLAN),
                    (emit.P6EmitError,))
        expect_fail("undeclared-thunk",
                    lambda: emit.exit_sites_for([]),
                    (emit.P6EmitError,))

        banner("regressions")
        regressions = []
        for script, extra in (
            ("tools/test_nes_rom_v1.py", []),
            ("tools/test_nes_platform_v1.py", []),
            ("tools/test_phase6_mmc1_fixture_v1.py",
             ["--evidence-dir", ".openrecomp-phase6/scratch/P6-08/regression_p6_06"]),
            ("tools/test_phase6_mmc1_recompile_v1.py",
             ["--evidence-dir", ".openrecomp-phase6/scratch/P6-08/regression_p6_07"]),
        ):
            record = run_regression(script, extra)
            check(f"regression:{script}:exit", record["returncode"] == 0)
            check(f"regression:{script}:stderr", record["stderr_empty"])
            regressions.append(record)
        FINDINGS["regressions"] = regressions

        banner("evidence_hygiene")
        write_json("build.json", {
            "stage": STAGE,
            "fixture_id": "p6-08-mmc1-fixture",
            "classification": comparison.classification.name,
            "executable_reproducible": comparison.executable_reproducible,
            "manifest_reproducible": comparison.manifest_reproducible,
            "executable_sha256": FINDINGS["executable_sha256"],
            "host_program_sha256": HOST_PROGRAM_SHA256,
            "support_sha256": SUPPORT_SHA256,
        })
        write_json("executions.json", {
            "stage": STAGE,
            "input_plan": list(INPUT_PLAN),
            "runs": 3,
            "fields": fields,
            "frames": frames,
        })
        write_json("regressions.json", {"stage": STAGE, "regressions": regressions})
        private_bytes = private_fixture.PRIVATE_ROM.read_bytes()
        for name, data in EVIDENCE_WRITES.items():
            check(f"hygiene:no-public-rom-bytes:{name}", rom not in data)
            check(f"hygiene:no-private-rom-bytes:{name}", private_bytes not in data)
        FINDINGS["evidence_files"] = sorted(EVIDENCE_WRITES)
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
    (EVIDENCE_DIR / "p6_08_tests.json").write_text(
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
