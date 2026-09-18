#!/usr/bin/env python3
"""OpenRecomp Phase-5 host emission + NES platform adapter gate (P5-08).

Verifies deterministic emission of the 6502 host translation and the bounded
NES runtime support, their reproducible native build through the shared
Phase-2 build pipeline, the native smoke execution, the emitted-ABI boundary
(only typed `or_rt_*` externs), and fail-closed emission for undeclared
indirect sites and undocumented opcodes.

On success it emits::

    OPENRECOMP_P5_08=PASS
    OPENRECOMP_PHASE5_HOST_EMIT_V1=PASS tests=<count>
    OPENRECOMP_PHASE5_NES_PLATFORM_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE5_GENERAL_NES_COMPATIBILITY=NOT_PROVEN
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
for entry in (str(ROOT), str(ROOT / ".openrecomp-phase5" / "src"), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import p5_emit_v1 as emit  # noqa: E402
import p5_fixture_build_v1 as fixture_build  # noqa: E402
import p5_frontier_v1 as frontier  # noqa: E402
import p5_ines_v1 as ingestion  # noqa: E402
import p5_structure_v1 as structure  # noqa: E402
import p5_support_v1 as support_module  # noqa: E402
from openrecomp.frontends import nes6502 as bridge  # noqa: E402
from openrecomp.program_model import DecodedInstruction, EvidenceClass, InstructionFlow  # noqa: E402

STAGE = "P5-08"
STAGE_MARKER = "OPENRECOMP_P5_08"
FEATURE_MARKER = "OPENRECOMP_PHASE5_HOST_EMIT_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE5_NES_PLATFORM_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE5_GENERAL_NES_COMPATIBILITY"

INPUT_PLAN = (0x01, 0x00, 0x04, 0x80, 0x00, 0x00, 0x00, 0x00)
EXPECTED_CASES = 231
EXPECTED_STEPS = 90904
EXPECTED_PC = "0xC0FD"
EXPECTED_FRAMES = 11
EXPECTED_NMI = 8
EXPECTED_CLOCK = 298327
EXPECTED_A = "0x00"
EXPECTED_X = "0x08"
EXPECTED_Y = "0x01"
EXPECTED_SP = "0xFF"
EXPECTED_P = "0x27"
EXPECTED_RAM_FNV = "0x2FC4A54B3F0C22CF"
EXPECTED_PPU_FNV = "0xCF103950DA2AD813"
EXPECTED_STATE_FNV = "0x440A095E452B3BA9"
EXPECTED_FRAMES_TRANSCRIPT = (
    "frame[0]=01,C42A06F7E7A28E25,39E9FBAE5A7B29A5",
    "frame[1]=00,C42A06F7E7A28E25,39E9FBAE5A7B29A5",
    "frame[2]=04,C42A06F7E7A28E25,39E9FBAE5A7B29A5",
    "frame[3]=80,3DBFA299A64BD805,470FE6BE14FF72F9",
    "frame[4]=00,3DBFA299A64BD805,CF103950DA2AD813",
    "frame[5]=00,3DBFA299A64BD805,CF103950DA2AD813",
    "frame[6]=00,3DBFA299A64BD805,CF103950DA2AD813",
    "frame[7]=00,3DBFA299A64BD805,CF103950DA2AD813",
    "frame[8]=00,3DBFA299A64BD805,CF103950DA2AD813",
    "frame[9]=00,3DBFA299A64BD805,CF103950DA2AD813",
    "frame[10]=00,3DBFA299A64BD805,CF103950DA2AD813",
)
FORBIDDEN_CALLS = ("system(", "popen(", "exec(", "fork(", "dlopen(",
                   "LoadLibrary", "CreateProcess")

REGRESSIONS = (
    ("tools/test_host_emitter_v1.py", []),
    ("tools/test_build_pipeline_v1.py", []),
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


def lf_normalize(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def canonical(document: Any) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_json(name: str, document: Any) -> None:
    EVIDENCE_WRITES[name] = canonical(document)


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
        [sys.executable, str(ROOT / script), *extra],
        cwd=str(ROOT), capture_output=True)
    return {
        "script": script,
        "returncode": completed.returncode,
        "stdout_bytes": len(completed.stdout),
        "stdout_sha256_raw": sha256_bytes(completed.stdout),
        "stdout_sha256_lf": sha256_bytes(lf_normalize(completed.stdout)),
        "stderr_bytes": len(completed.stderr),
        "stderr_empty": len(completed.stderr) == 0,
    }


def emit_sources(rom: bytes, metadata: dict, inventory: dict, plan):
    image = frontier.build_cpu_image(rom, 16, metadata["prg_size"])
    start, end = frontier.code_region_from_metadata(metadata)
    instructions = bridge.bridge_region(image, entry=start, end=end)
    analysis = structure.build_structure(rom, metadata, inventory)
    exit_sites = {item["address"]: emit.EXIT_SERVICE_NAME
                  for item in analysis["indirect_classifications"]}
    program = emit.emit_program(instructions, metadata, exit_sites)
    support = support_module.emit_support(rom, inventory, plan,
                                          rom_sha256=metadata["rom_sha256"])
    return instructions, program, support


def parse_observable(stdout: str) -> tuple[dict[str, str], list[str]]:
    fields: dict[str, str] = {}
    frames: list[str] = []
    for line in stdout.splitlines():
        if line.startswith("frame["):
            frames.append(line)
        elif "=" in line:
            key, value = line.split("=", 1)
            fields[key] = value
    return fields, frames


def main() -> int:
    parser = argparse.ArgumentParser(description="P5-08 host emission gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase5/evidence/P5-08")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}

    print("=== P5-08 Host Emission / NES Platform Adapter Gate ===", flush=True)
    failure: str | None = None
    try:
        banner("fixtures")
        rom, metadata = fixture_build.build()
        inventory = ingestion.ingest(rom, source_label="public_fixture").to_document()

        banner("emission")
        instructions, program_a, support_a = emit_sources(
            rom, metadata, inventory, INPUT_PLAN)
        _, program_b, support_b = emit_sources(rom, metadata, inventory, INPUT_PLAN)
        check("emission:deterministic-program", program_a == program_b)
        check("emission:deterministic-support", support_a == support_b)
        check("emission:case-count", program_a.count("    case 0x") == EXPECTED_CASES)
        check("emission:switch", program_a.count("switch (g_pc)") == 1)
        check("emission:advance",
              program_a.count("or_rt_advance(") >= EXPECTED_CASES)
        for token in FORBIDDEN_CALLS:
            check(f"emission:no-forbidden:{token}", token not in program_a
                  and token not in support_a)
        check("emission:typed-abi",
              "or_rt_memory_read" in program_a
              and "or_rt_memory_write" in program_a
              and "or_rt_host_call" in program_a)
        check("emission:no-guest-code-execution",
              "void (*" not in program_a and "void (*" not in support_a
              and "g_prg" in support_a)
        check("emission:public-rom-embedded-in-support",
              all(f"0x{value:02X}" in support_a
                  for value in rom[16:32]))
        FINDINGS["program_sha256"] = sha256_bytes(program_a.encode("utf-8"))
        FINDINGS["support_sha256"] = sha256_bytes(support_a.encode("utf-8"))

        banner("emission_negative")
        no_sites = tuple(instruction for instruction in instructions)
        expect_fail("undeclared-indirect-site",
                    lambda: emit.emit_cases(no_sites, {}),
                    (emit.HostEmitError,))
        bad_site = {instructions[0].address: emit.EXIT_SERVICE_NAME}
        expect_fail("wrong-indirect-site",
                    lambda: emit.emit_cases(no_sites, bad_site),
                    (emit.HostEmitError,))
        undocumented = DecodedInstruction(
            address=0xC0FF, op="jam", size_bytes=1, flow=InstructionFlow.NORMAL,
            metadata={"adapter_fields": {"word": 0x03}})
        expect_fail("undocumented-opcode",
                    lambda: emit.emit_cases(
                        (undocumented,), {}),
                    (emit.HostEmitError,))

        banner("native_build")
        workspace = ROOT / ".openrecomp-phase5" / "build" / "P5-08" / "gate"
        if workspace.exists():
            shutil.rmtree(workspace)
        comparison = support_module.build_native(
            program_a, support_a, fixture_id="p5-08-nes-fixture",
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

        banner("native_smoke")
        outputs = []
        for _ in range(3):
            completed = subprocess.run([str(executable)], capture_output=True,
                                       text=True, encoding="utf-8",
                                       errors="replace", timeout=600)
            check("smoke:exit-code", completed.returncode == 0)
            outputs.append(completed.stdout)
        check("smoke:identical-output", len(set(outputs)) == 1)
        fields, frames = parse_observable(outputs[0])
        check("smoke:failed", fields["failed"] == "0" and fields["error"] == "")
        check("smoke:exit", fields["exit"] == "1")
        check("smoke:steps", fields["steps"] == str(EXPECTED_STEPS))
        check("smoke:pc", fields["pc"] == EXPECTED_PC)
        check("smoke:cpu",
              fields["a"] == EXPECTED_A and fields["x"] == EXPECTED_X
              and fields["y"] == EXPECTED_Y and fields["sp"] == EXPECTED_SP
              and fields["p"] == EXPECTED_P)
        check("smoke:frames", fields["frames"] == str(EXPECTED_FRAMES))
        check("smoke:nmi", fields["nmi"] == str(EXPECTED_NMI))
        check("smoke:clock", fields["clock"] == str(EXPECTED_CLOCK))
        check("smoke:exit-arg", fields["exit_arg"] == "0x0000C0FD")
        check("smoke:ram-digest", fields["ram_fnv1a64"] == EXPECTED_RAM_FNV)
        check("smoke:ppu-digest", fields["ppu_fnv1a64"] == EXPECTED_PPU_FNV)
        check("smoke:state-digest",
              fields["state_fnv1a64"] == EXPECTED_STATE_FNV)
        check("smoke:frame-transcript",
              tuple(frames) == EXPECTED_FRAMES_TRANSCRIPT)

        banner("regressions")
        regressions = []
        for script, extra in REGRESSIONS:
            record = run_regression(script, extra)
            check(f"regression:{script}:exit", record["returncode"] == 0)
            check(f"regression:{script}:stderr", record["stderr_empty"])
            regressions.append(record)
        FINDINGS["regressions"] = regressions

        banner("evidence")
        write_json("emission.json", {
            "stage": STAGE,
            "exit_service": emit.EXIT_SERVICE_NAME,
            "exit_service_id": emit.EXIT_SERVICE_ID,
            "input_plan": list(INPUT_PLAN),
            "program_sha256": FINDINGS["program_sha256"],
            "support_sha256": FINDINGS["support_sha256"],
            "cases": EXPECTED_CASES,
            "native_build": {
                "classification": comparison.classification.name,
                "executable_sha256": FINDINGS["executable_sha256"],
                "toolchain": {"compiler": "clang-cl.exe", "linker": "lld-link.exe"},
            },
        })
        write_json("observable.json", {
            "stage": STAGE,
            "fields": fields,
            "frames": frames,
        })
        write_json("regressions.json", {"stage": STAGE, "regressions": regressions})
        for name, data in EVIDENCE_WRITES.items():
            check(f"hygiene:no-private-rom-sha:{name}",
                  b"2a9345e608ec0c57470dc6658ce8199ddea9c18076134d9ef2a56f91b0a066d1"
                  not in data)
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
    (EVIDENCE_DIR / "p5_08_tests.json").write_text(
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
