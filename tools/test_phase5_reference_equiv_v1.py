#!/usr/bin/env python3
"""OpenRecomp Phase-5 independent NES reference equivalence gate (P5-10).

Runs the same bounded public fixture and declared controller plans through:

* the native translation + bounded NES runtime support (P5-08/P5-09), and
* the frozen independently written `ReferenceNES6502` driven through the
  frozen independent `NesMachine` platform with the identical P5-07
  scheduling policy and the same declared run-exit service interception.

Compares CPU state, RAM/PPU/VRAM/palette/OAM, frame transcript, interrupt
counts, exit state and the canonical state digest exactly, and verifies the
comparison is sensitive to a tampered scheduling policy.

On success it emits::

    OPENRECOMP_P5_10=PASS
    OPENRECOMP_PHASE5_REFERENCE_EQUIVALENCE_V1=PASS tests=<count>
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
import p5_reference_v1 as reference_module  # noqa: E402
import p5_structure_v1 as structure  # noqa: E402
import p5_support_v1 as support_module  # noqa: E402
from openrecomp.frontends import nes6502 as bridge  # noqa: E402

STAGE = "P5-10"
STAGE_MARKER = "OPENRECOMP_P5_10"
FEATURE_MARKER = "OPENRECOMP_PHASE5_REFERENCE_EQUIVALENCE_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE5_NES_PLATFORM_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE5_GENERAL_NES_COMPATIBILITY"

PLANS = {
    "none": (0x00,) * 8,
    "a": (0x01,) * 8,
    "right": (0x80,) * 8,
    "a_right": (0x81,) * 8,
}
COMPARED_FIELDS = (
    "failed", "error", "exit", "steps", "pc", "a", "x", "y", "sp", "p",
    "frames", "nmi", "clock", "exit_arg", "ram_fnv1a64", "ppu_fnv1a64",
    "state_fnv1a64",
)

REGRESSIONS = (
    ("tools/test_nes_headless_v1.py", []),
    ("tools/test_nes6502_state_v1.py", []),
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


def native_run(rom: bytes, metadata: dict, inventory: dict, instructions,
               plan, name: str) -> dict[str, Any]:
    support = support_module.emit_support(rom, inventory, plan,
                                          rom_sha256=metadata["rom_sha256"])
    analysis = structure.build_structure(rom, metadata, inventory)
    exit_sites = {item["address"]: emit.EXIT_SERVICE_NAME
                  for item in analysis["indirect_classifications"]}
    program = emit.emit_program(instructions, metadata, exit_sites)
    workspace = ROOT / ".openrecomp-phase5" / "build" / "P5-10" / name
    if workspace.exists():
        shutil.rmtree(workspace)
    comparison = support_module.build_native(
        program, support, fixture_id=f"p5-10-{name}", workspace=workspace)
    executable = workspace / "run1" / "program.exe"
    outputs = []
    for _ in range(2):
        completed = subprocess.run([str(executable)], capture_output=True,
                                   text=True, encoding="utf-8",
                                   errors="replace", timeout=600)
        if completed.returncode != 0:
            raise AssertionError(f"{name}: native exit {completed.returncode}")
        outputs.append(completed.stdout)
    fields, frames = parse_observable(outputs[0])
    return {
        "classification": comparison.classification.name,
        "deterministic": len(set(outputs)) == 1,
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
        mismatches.append({
            "field": "frames",
            "native": native["frames"],
            "reference": reference["frames"],
        })
    if native["exit_word"] != reference["exit_word"]:
        mismatches.append({
            "field": "exit_word",
            "native": native["exit_word"],
            "reference": reference["exit_word"],
        })
    return {"equivalent": not mismatches, "mismatches": mismatches}


def main() -> int:
    parser = argparse.ArgumentParser(description="P5-10 reference equivalence gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase5/evidence/P5-10")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}

    print("=== P5-10 Independent NES Reference Equivalence Gate ===", flush=True)
    failure: str | None = None
    try:
        banner("fixtures")
        rom, metadata = fixture_build.build()
        inventory = ingestion.ingest(rom, source_label="public_fixture").to_document()
        image = frontier.build_cpu_image(rom, 16, metadata["prg_size"])
        start, end = frontier.code_region_from_metadata(metadata)
        instructions = bridge.bridge_region(image, entry=start, end=end)

        banner("equivalence")
        records: dict[str, Any] = {}
        for name, plan in PLANS.items():
            native = native_run(rom, metadata, inventory, instructions, plan, name)
            check(f"{name}:native-reproducible",
                  native["classification"] == "EXECUTABLE_REPRODUCIBLE")
            check(f"{name}:native-deterministic", native["deterministic"])
            reference = reference_module.run_reference(rom, plan)
            comparison = compare(native, reference)
            records[name] = {
                "plan": list(plan),
                "native": native,
                "reference": {
                    "fields": reference["fields"],
                    "frames": reference["frames"],
                    "exit_word": reference["exit_word"],
                },
                "comparison": comparison,
            }
            check(f"{name}:equivalent", comparison["equivalent"])
            check(f"{name}:cpu-state",
                  native["fields"]["pc"] == reference["fields"]["pc"]
                  and native["fields"]["p"] == reference["fields"]["p"])
            check(f"{name}:digests",
                  native["fields"]["state_fnv1a64"]
                  == reference["fields"]["state_fnv1a64"]
                  and native["fields"]["ram_fnv1a64"]
                  == reference["fields"]["ram_fnv1a64"]
                  and native["fields"]["ppu_fnv1a64"]
                  == reference["fields"]["ppu_fnv1a64"])
            check(f"{name}:interrupts",
                  native["fields"]["nmi"] == reference["fields"]["nmi"]
                  and native["fields"]["frames"] == reference["fields"]["frames"])
            check(f"{name}:exit",
                  native["fields"]["exit"] == "1"
                  and native["fields"]["exit_arg"] == reference["fields"]["exit_arg"])

        banner("sensitivity")
        tampered = reference_module.run_reference(
            rom, PLANS["none"], nmi_entry_cost=9)
        check("sensitivity:nmi-cost",
              tampered["fields"] != records["none"]["reference"]["fields"])
        wrong_frames = reference_module.run_reference(
            rom, PLANS["none"],
            frame_units=reference_module.platform.FRAME_CLOCK_UNITS + 1)
        check("sensitivity:frame-length",
              wrong_frames["fields"] != records["none"]["reference"]["fields"])

        banner("regressions")
        regressions = []
        for script, extra in REGRESSIONS:
            record = run_regression(script, extra)
            check(f"regression:{script}:exit", record["returncode"] == 0)
            check(f"regression:{script}:stderr", record["stderr_empty"])
            regressions.append(record)
        FINDINGS["regressions"] = regressions

        banner("evidence")
        write_json("equivalence.json", {
            "stage": STAGE,
            "plans": {name: list(plan) for name, plan in PLANS.items()},
            "records": records,
        })
        write_json("sensitivity.json", {
            "stage": STAGE,
            "nmi_cost_tamper_fields": tampered["fields"],
            "wrong_frame_length_fields": wrong_frames["fields"],
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
    (EVIDENCE_DIR / "p5_10_tests.json").write_text(
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
