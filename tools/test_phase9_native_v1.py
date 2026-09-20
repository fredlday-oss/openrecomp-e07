#!/usr/bin/env python3
"""OpenRecomp Phase-9 native build and deterministic execution gate (P9-10).

The gate proves the bounded PS1 public fixture is recompiled to native host
code through the existing architecture-neutral path and executes
deterministically with an independent reference agreeing on every observable:

* deterministic four-file emission set (`program.c`, `p9_image_v1.c`,
  `p9_runtime_support.c`, `p9_driver.c`) with stable hashes; the guest image is
  inert data and `program.c` contains no machine code;
* reproducible native build through `openrecomp.build_pipeline`;
* repeated execution with byte-identical stdout;
* the independently structured PS-X EXE reference
  (`.openrecomp-phase9/src/p9_reference_psx_v1.py`) agrees on exit status, all
  32 registers and digest, RAM digest, typed platform event counts/digests and
  access counters, with no excluded observables.

On success it emits::

    OPENRECOMP_P9_10=PASS
    OPENRECOMP_PHASE9_NATIVE_EXECUTION_V1=PASS tests=<count>
    OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN
    OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN

Usage:

    python tools/test_phase9_native_v1.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import traceback


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / ".openrecomp-phase3" / "src"))
sys.path.insert(0, str(ROOT / ".openrecomp-phase8" / "src"))
sys.path.insert(0, str(ROOT / ".openrecomp-phase9" / "src"))
sys.path.insert(0, str(ROOT / ".openrecomp-phase9" / "fixture"))

import p9_emission_v1 as emission  # noqa: E402
import p9_image_bridge_v1 as bridge  # noqa: E402
import p9_memory_map_v1 as memory_map  # noqa: E402
import p9_psx_exe_v1 as psx  # noqa: E402
import p9_public_fixture_v1 as fixture  # noqa: E402
import p9_reference_psx_v1 as reference  # noqa: E402
from openrecomp import build_pipeline as bp  # noqa: E402

STAGE = "P9-10"
FEATURE_MARKER = "OPENRECOMP_PHASE9_NATIVE_EXECUTION_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE9_HERCULES_PLAYABILITY"
NOT_PROVEN = "NOT_PROVEN"

SUPPORT_SOURCE = ROOT / ".openrecomp-phase9" / "runtime" / "p9_runtime_support.c"
DRIVER_SOURCE = ROOT / ".openrecomp-phase9" / "runtime" / "p9_observable_driver.c"
WORKSPACE = ROOT / ".openrecomp-phase9" / "build" / "P9-10"

COMPARED_FIELDS = (
    "failed",
    "error",
    "exit_status",
    "registers_digest",
    "memory_digest",
    "gpu_events",
    "gpu_digest",
    "input_events",
    "input_digest",
    "spu_events",
    "spu_digest",
    "cdrom_events",
    "cdrom_digest",
    "reads",
    "writes",
    "denied",
    "host_calls",
)

RESULTS: list[dict[str, str]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    RESULTS.append({"check": label, "status": "PASS" if condition else "FAIL", "detail": detail})
    if not condition:
        raise AssertionError(f"{label}: condition failed ({detail})")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: pathlib.Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def parse_native(stdout: str) -> dict:
    parsed: dict = {"registers": {}}
    for line in stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.strip().split("=", 1)
        if key.startswith("r") and len(key) == 3 and key[1:].isdigit():
            parsed["registers"][int(key[1:])] = value
        elif key == "registers":
            parsed["registers_digest"] = value
        elif key in ("failed", "gpu_events", "input_events", "spu_events", "cdrom_events", "reads", "writes", "denied", "host_calls"):
            parsed[key] = int(value)
        else:
            parsed[key] = value
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--evidence-dir",
        default=".openrecomp-phase9/evidence/P9-10",
        help="evidence directory relative to the repository root",
    )
    options = parser.parse_args()
    evidence = (ROOT / options.evidence_dir).resolve()

    try:
        # --- deterministic emission ----------------------------------------
        public_bytes = fixture.build_fixture()
        public_image = psx.ingest(public_bytes)
        public_contract = memory_map.build_contract(public_image)
        public_flat = memory_map.flat_image(public_image)
        public = bridge.analyze(public_image, public_contract, public_flat)
        check("emission:structure-built", public.structure is not None, str(public.structure_error))

        build_set = emission.build_build_set(
            public.structure,
            public_contract,
            public_flat,
            SUPPORT_SOURCE.read_text(encoding="utf-8"),
            DRIVER_SOURCE.read_text(encoding="utf-8"),
            sha256(public_bytes),
        )
        build_set_again = emission.build_build_set(
            public.structure,
            public_contract,
            public_flat,
            SUPPORT_SOURCE.read_text(encoding="utf-8"),
            DRIVER_SOURCE.read_text(encoding="utf-8"),
            sha256(public_bytes),
        )
        check("emission:stable-hashes", build_set["hashes"] == build_set_again["hashes"], "stable content hashes")
        check("emission:file-set", tuple(build_set["files"]) == emission.EMISSION_NAMES, ",".join(build_set["files"]))
        check("emission:program-fingerprint", build_set["program_fingerprint"] == build_set_again["program_fingerprint"], build_set["program_fingerprint"])
        program_text = build_set["files"][emission.PROGRAM_NAME]
        check("emission:program-no-machine-code", public_image.payload.hex() not in program_text.lower(), "no payload hex in program.c")
        check(
            "emission:program-has-abi",
            "or_rt_memory_read" in program_text and "openrecomp_run" in program_text,
            "runtime ABI surface",
        )
        document = emission.emission_document(build_set)
        write_json(evidence / "emission.json", document)

        # --- reproducible native build --------------------------------------
        if WORKSPACE.exists():
            shutil.rmtree(WORKSPACE)
        comparison = bp.build_generated_host(
            lambda: build_set["files"][emission.PROGRAM_NAME],
            support_sources=(
                bp.BuildSource(emission.IMAGE_NAME, bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE, build_set["files"][emission.IMAGE_NAME].encode("utf-8")),
                bp.BuildSource(emission.SUPPORT_NAME, bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE, build_set["files"][emission.SUPPORT_NAME].encode("utf-8")),
                bp.BuildSource(emission.DRIVER_NAME, bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE, build_set["files"][emission.DRIVER_NAME].encode("utf-8")),
            ),
            config=bp.BuildConfig(fixture_id="p9-10-native", smoke_test=False, run_count=2),
            workspace=WORKSPACE,
            keep_workspace=True,
        )
        check("build:status", all(run.manifest.build_status is bp.BuildStatus.OK for run in comparison.runs), str([run.manifest.build_status.value for run in comparison.runs]))
        executable = WORKSPACE / "run1" / "program.exe"
        check("build:executable", executable.is_file(), str(executable))
        executable_sha = sha256(executable.read_bytes())

        # --- deterministic execution ----------------------------------------
        completed = subprocess.run([str(executable)], capture_output=True, timeout=600)
        check("native:exit", completed.returncode == 0, str(completed.returncode))
        check("native:stderr", completed.stderr == b"", completed.stderr[:120].decode("ascii", "replace"))
        first = completed.stdout
        completed2 = subprocess.run([str(executable)], capture_output=True, timeout=600)
        check("native:stdout-identical", completed2.stdout == first, "byte-identical")
        native = parse_native(first.decode("utf-8"))
        check("native:not-failed", native.get("failed") == 0, str(native.get("failed")))
        check("native:exit-status", native.get("exit_status") == "0x00000002", str(native.get("exit_status")))
        check("native:no-denied", native.get("denied") == 0, str(native.get("denied")))

        # --- independent reference ------------------------------------------
        run = reference.load_and_run(public_bytes)
        observed = run.to_observables()
        check("reference:steps", 0 < run.steps < reference.STEP_LIMIT, str(run.steps))
        check("reference:exit-status", observed["exit_status"] == "0x00000002", observed["exit_status"])

        native_fields = {
            "failed": native.get("failed"),
            "error": native.get("error"),
            "exit_status": native.get("exit_status"),
            "registers_digest": native.get("registers_digest"),
            "memory_digest": native.get("memory"),
            "gpu_events": native.get("gpu_events"),
            "gpu_digest": native.get("gpu"),
            "input_events": native.get("input_events"),
            "input_digest": native.get("input"),
            "spu_events": native.get("spu_events"),
            "spu_digest": native.get("spu"),
            "cdrom_events": native.get("cdrom_events"),
            "cdrom_digest": native.get("cdrom"),
            "reads": native.get("reads"),
            "writes": native.get("writes"),
            "denied": native.get("denied"),
            "host_calls": native.get("host_calls"),
        }
        reference_fields = {key: observed[key] for key in COMPARED_FIELDS}
        mismatches = {
            key: {"native": native_fields[key], "reference": reference_fields[key]}
            for key in COMPARED_FIELDS
            if native_fields[key] != reference_fields[key]
        }
        check("equivalence:fields", not mismatches, json.dumps(mismatches, sort_keys=True))
        for index in range(32):
            native_register = native["registers"].get(index)
            reference_register = observed["registers"][f"r{index:02d}"]
            check(f"equivalence:r{index:02d}", native_register == reference_register, f"native={native_register} reference={reference_register}")

        native_record = {
            "schema": "openrecomp-phase9-native-execution-v1",
            "stage": STAGE,
            "fixture_sha256": sha256(public_bytes),
            "executable_sha256": executable_sha,
            "stdout_bytes": len(first),
            "stdout_sha256": sha256(first),
            "observable": native_fields,
            "registers": {f"r{index:02d}": native["registers"].get(index) for index in range(32)},
        }
        write_json(evidence / "native_execution.json", native_record)
        reference_record = {
            "schema": "openrecomp-phase9-reference-psx-v1",
            "stage": STAGE,
            "fixture_sha256": sha256(public_bytes),
            "observable": observed,
        }
        write_json(evidence / "reference.json", reference_record)
        write_json(
            evidence / "equivalence.json",
            {
                "schema": "openrecomp-phase9-equivalence-v1",
                "stage": STAGE,
                "excluded_observables": [],
                "mismatches": {},
                "compared_fields": list(COMPARED_FIELDS),
                "register_count": 32,
            },
        )
    except AssertionError as exc:
        RESULTS.append({"check": "gate:assertion", "status": "FAIL", "detail": str(exc)})
    except Exception as exc:  # fail closed with a stable record
        detail = f"{type(exc).__name__}: {exc} @ {traceback.extract_tb(exc.__traceback__)[-1].name}:{traceback.extract_tb(exc.__traceback__)[-1].lineno}"
        RESULTS.append({"check": "gate:exception", "status": "FAIL", "detail": detail})

    failed = [item for item in RESULTS if item["status"] == "FAIL"]
    status = "PASS" if not failed else "FAIL"
    results = sorted(RESULTS, key=lambda item: item["check"])
    record = {
        "stage": STAGE,
        "stage_name": "Native build and deterministic execution",
        "status": status,
        "tests": len(results),
        "passed": sum(1 for item in results if item["status"] == "PASS"),
        "failed": len(failed),
        "checks": results,
        "failure": None if not failed else [item["check"] for item in failed],
    }
    write_json(evidence / "p9_10_tests.json", record)

    for item in results:
        print(f"{item['status']}: {item['check']}")
    print(f"OPENRECOMP_P9_10={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(results)}")
    print(f"{TERMINAL_MARKER}={NOT_PROVEN}")
    print(f"{GENERAL_MARKER}={NOT_PROVEN}")
    print(f"{PLAYABILITY_MARKER}={NOT_PROVEN}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
