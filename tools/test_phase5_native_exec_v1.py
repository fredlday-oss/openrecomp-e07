#!/usr/bin/env python3
"""OpenRecomp Phase-5 native execution gate (P5-09).

Executes the native translation of the legally clean public fixture under
multiple declared controller input plans and verifies meaningful interactive
behaviour across the CPU + memory + input + timing + graphics/platform
boundaries:

* every plan builds reproducibly and runs deterministically;
* the guest records the exact input byte per frame in its transcript;
* input-derived guest RAM state (A button) and PPU/OAM observables (RIGHT)
  change exactly as the fixture documents, while nametable graphics are
  unaffected by controller input.

On success it emits::

    OPENRECOMP_P5_09=PASS
    OPENRECOMP_PHASE5_NATIVE_EXECUTION_V1=PASS tests=<count>
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

STAGE = "P5-09"
STAGE_MARKER = "OPENRECOMP_P5_09"
FEATURE_MARKER = "OPENRECOMP_PHASE5_NATIVE_EXECUTION_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE5_NES_PLATFORM_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE5_GENERAL_NES_COMPATIBILITY"

PLANS = {
    "none": (0x00,) * 8,
    "a": (0x01,) * 8,
    "right": (0x80,) * 8,
    "a_right": (0x81,) * 8,
}
EXPECTED_FRAMES = 11
EXPECTED_NMI = 8

REGRESSIONS = (
    ("tools/test_nes6502_host_emitter_v1.py",
     ["--evidence-dir", ".openrecomp-phase5/scratch/regression_p5_09_p2_21"]),
    ("tools/test_nes_runtime_bridge_v1.py",
     ["--evidence-dir", ".openrecomp-phase5/scratch/regression_p5_09_p2_22"]),
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


def reverse_byte(value: int) -> int:
    """The fixture's serial read shifts each new bit into the LSB, so the
    guest-side input byte is the bit-reversed platform controller byte."""
    result = 0
    for index in range(8):
        result |= ((value >> index) & 1) << (7 - index)
    return result


def build_and_run(rom: bytes, metadata: dict, inventory: dict,
                  instructions, plan, name: str) -> dict[str, Any]:
    support = support_module.emit_support(rom, inventory, plan,
                                          rom_sha256=metadata["rom_sha256"])
    program, _ = emit_sources_pair(rom, metadata, inventory, instructions, plan)
    workspace = ROOT / ".openrecomp-phase5" / "build" / "P5-09" / name
    if workspace.exists():
        shutil.rmtree(workspace)
    comparison = support_module.build_native(
        program, support, fixture_id=f"p5-09-{name}", workspace=workspace)
    executable = workspace / "run1" / "program.exe"
    outputs = []
    for _ in range(2):
        completed = subprocess.run([str(executable)], capture_output=True,
                                   text=True, encoding="utf-8",
                                   errors="replace", timeout=600)
        if completed.returncode != 0:
            raise AssertionError(f"{name}: executable exit {completed.returncode}")
        outputs.append(completed.stdout)
    fields, frames = parse_observable(outputs[0])
    return {
        "plan": list(plan),
        "classification": comparison.classification.name,
        "executable_sha256": sha256_bytes(executable.read_bytes()),
        "deterministic": len(set(outputs)) == 1,
        "fields": fields,
        "frames": frames,
        "stdout_sha256": sha256_bytes(outputs[0].encode("utf-8")),
    }


def emit_sources_pair(rom: bytes, metadata: dict, inventory: dict,
                      instructions, plan):
    image = frontier.build_cpu_image(rom, 16, metadata["prg_size"])
    start, end = frontier.code_region_from_metadata(metadata)
    analysis = structure.build_structure(rom, metadata, inventory)
    exit_sites = {item["address"]: emit.EXIT_SERVICE_NAME
                  for item in analysis["indirect_classifications"]}
    program = emit.emit_program(instructions, metadata, exit_sites)
    return program, None


def main() -> int:
    parser = argparse.ArgumentParser(description="P5-09 native execution gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase5/evidence/P5-09")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}

    print("=== P5-09 Native Execution Gate ===", flush=True)
    failure: str | None = None
    try:
        banner("fixtures")
        rom, metadata = fixture_build.build()
        inventory = ingestion.ingest(rom, source_label="public_fixture").to_document()
        image = frontier.build_cpu_image(rom, 16, metadata["prg_size"])
        start, end = frontier.code_region_from_metadata(metadata)
        instructions = bridge.bridge_region(image, entry=start, end=end)

        banner("executions")
        executions: dict[str, Any] = {}
        for name, plan in PLANS.items():
            record = build_and_run(rom, metadata, inventory, instructions, plan, name)
            executions[name] = record
            check(f"exec:{name}:reproducible",
                  record["classification"] == "EXECUTABLE_REPRODUCIBLE")
            check(f"exec:{name}:deterministic", record["deterministic"])
            fields = record["fields"]
            check(f"exec:{name}:ok",
                  fields["failed"] == "0" and fields["error"] == ""
                  and fields["exit"] == "1")
            check(f"exec:{name}:frames",
                  fields["frames"] == str(EXPECTED_FRAMES)
                  and fields["nmi"] == str(EXPECTED_NMI))
            expected_word = "".join(f"{reverse_byte(value):02X}" for value in plan)
            check(f"exec:{name}:input-transcript",
                  fields["exit_word"] == expected_word)
            check(f"exec:{name}:frame-transcript-length",
                  len(record["frames"]) == EXPECTED_FRAMES)

        banner("interactivity")
        none = executions["none"]
        plan_a = executions["a"]
        plan_right = executions["right"]
        plan_both = executions["a_right"]
        check("interactive:a-changes-ram",
              plan_a["fields"]["ram_fnv1a64"] != none["fields"]["ram_fnv1a64"])
        check("interactive:a-changes-ppu",
              plan_a["fields"]["ppu_fnv1a64"] != none["fields"]["ppu_fnv1a64"])
        check("interactive:right-changes-ram",
              plan_right["fields"]["ram_fnv1a64"] != none["fields"]["ram_fnv1a64"])
        check("interactive:right-keeps-ppu",
              plan_right["fields"]["ppu_fnv1a64"] == none["fields"]["ppu_fnv1a64"])
        check("interactive:combined-distinct",
              plan_both["fields"]["state_fnv1a64"]
              != plan_a["fields"]["state_fnv1a64"]
              and plan_both["fields"]["state_fnv1a64"]
              != plan_right["fields"]["state_fnv1a64"])
        check("interactive:plans-pairwise-distinct",
              len({record["fields"]["state_fnv1a64"]
                   for record in executions.values()}) == len(PLANS))
        tile_sets = {tuple(line.split(",")[1] for line in record["frames"])
                     for record in executions.values()}
        check("interactive:nametable-unchanged-by-input", len(tile_sets) == 1)
        check("interactive:frame-inputs-visible",
              [line.split(",")[0].split("=")[1]
               for line in plan_a["frames"]][:8]
              == ["01"] * 8)
        check("interactive:right-frame-inputs",
              [line.split(",")[0].split("=")[1]
               for line in plan_right["frames"]][:8]
              == ["80"] * 8)

        banner("regressions")
        regressions = []
        for script, extra in REGRESSIONS:
            record = run_regression(script, extra)
            check(f"regression:{script}:exit", record["returncode"] == 0)
            check(f"regression:{script}:stderr", record["stderr_empty"])
            regressions.append(record)
        FINDINGS["regressions"] = regressions

        banner("evidence")
        write_json("executions.json", {
            "stage": STAGE,
            "plans": {name: list(plan) for name, plan in PLANS.items()},
            "executions": executions,
        })
        write_json("interactivity.json", {
            "stage": STAGE,
            "digests": {
                name: {
                    "ram": record["fields"]["ram_fnv1a64"],
                    "ppu": record["fields"]["ppu_fnv1a64"],
                    "state": record["fields"]["state_fnv1a64"],
                    "steps": record["fields"]["steps"],
                    "clock": record["fields"]["clock"],
                }
                for name, record in executions.items()
            },
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
    (EVIDENCE_DIR / "p5_09_tests.json").write_text(
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
