#!/usr/bin/env python3
"""OpenRecomp Phase-8 independent reference equivalence gate (P8-09).

P8-09 executes the frozen real ELF under an independently structured MIPS32
reference (`.openrecomp-phase8/src/p8_reference_mips32_v1.py`: own ELF loader,
own decoder/interpreter, own memory/runtime contract; it does not import the
recompilation path) and compares every required observable against the P8-08
native result and the recorded P8-08 evidence.

No observable is excluded: the gate requires exact equality of the exit
status, all 32 boundary registers, the register-file digest, the guest memory
digest, the output transcript length and digest, and every event count.

On success it emits::

    OPENRECOMP_P8_09=PASS
    OPENRECOMP_PHASE8_REFERENCE_EQUIVALENCE_V1=PASS tests=<count>
    OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase8_reference_equivalence_v1.py
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / ".openrecomp-phase3" / "src"))
sys.path.insert(0, str(ROOT / ".openrecomp-phase8" / "src"))

import adapters.mips32 as mips32_adapter  # noqa: E402
import p3_code_frontier_v1 as frontier  # noqa: E402
import p3_elf_image_v1 as elf  # noqa: E402
import p3_target_mips32_v1 as target  # noqa: E402
import p8_emission_v1 as emission  # noqa: E402
import p8_memory_contract_v1 as contract_v1  # noqa: E402
import p8_reference_mips32_v1 as reference  # noqa: E402
import p8_structure_v1 as structure_bridge  # noqa: E402
from openrecomp import build_pipeline as bp  # noqa: E402
from openrecomp.program_model import ProgramSource  # noqa: E402

EVIDENCE_DIR = ROOT / ".openrecomp-phase8" / "evidence" / "P8-09"
WORKSPACE = ROOT / ".openrecomp-phase8" / "build" / "P8-09"

STAGE = "P8-09"
STAGE_MARKER = "OPENRECOMP_P8_09"
FEATURE_MARKER = "OPENRECOMP_PHASE8_REFERENCE_EQUIVALENCE_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY"
NOT_PROVEN = "NOT_PROVEN"

FIXTURE_ELF = ROOT / ".openrecomp-phase8" / "build" / "P8-01" / "candidate-a" / "p8_aes128_mips32_O1.elf"
FIXTURE_SHA256 = "0a90f47754f6331b868ec09ad23c451fc2c73925a43897fa62a696b0d40dde65"
P8_08_EVIDENCE = ROOT / ".openrecomp-phase8" / "evidence" / "P8-08" / "native_execution.json"
SUPPORT_SOURCE = ROOT / ".openrecomp-phase8" / "runtime" / "p8_runtime_support.c"
DRIVER_SOURCE = ROOT / ".openrecomp-phase8" / "runtime" / "p8_observable_driver.c"
NATIVE_RUNS = 2

FORBIDDEN_REFERENCE_IMPORTS = (
    "host_emitter",
    "p8_mips32_semantics_v1",
    "p8_emission_v1",
    "p8_runtime_support",
    "p8_structure_v1",
    "p3_elf_image_v1",
    "p3_code_frontier_v1",
)

RESULTS: list[dict[str, str]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL", "detail": detail})
        raise AssertionError(f"{label}: condition failed ({detail})")
    RESULTS.append({"check": label, "status": "PASS", "detail": detail})
    print(f"PASS: {label}")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def evidence_json(payload: object) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_evidence(name: str, payload: object) -> None:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    (EVIDENCE_DIR / name).write_bytes(evidence_json(payload))


def parse_native(stdout: str) -> dict:
    record: dict = {"registers": {}}
    for line in stdout.splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.startswith("r") and len(key) == 3 and key[1:].isdigit():
            record["registers"][int(key[1:])] = value
        elif key == "registers":
            record["registers_digest"] = value
        elif key in ("transcript_len", "reads", "writes", "host_calls", "denied"):
            record[key] = int(value)
        else:
            record[key] = value
    return record


def build_and_run_native():
    data = FIXTURE_ELF.read_bytes()
    ingested = elf.ingest(data, target.MIPS32_O32)
    region = ingested.parsed.executable_regions()[0]
    analysis = frontier.analyze(ingested.image.read_u32, region.p_vaddr, region.p_vaddr + region.p_memsz, ingested.parsed.header.e_entry)
    source = ProgramSource(
        mips32_adapter.info.architecture_id,
        adapter="adapters.mips32",
        address_width_bits=32,
        endianness="little",
        input_sha256=sha256_bytes(data),
    )
    structure = structure_bridge.analyze_structure(analysis, source=source, entry=ingested.parsed.header.e_entry)
    contract = contract_v1.build_contract(ingested)
    image = contract_v1.flat_image(ingested)
    build = emission.build_build_set(
        structure,
        contract,
        image,
        SUPPORT_SOURCE.read_text(encoding="utf-8"),
        DRIVER_SOURCE.read_text(encoding="utf-8"),
        FIXTURE_SHA256,
    )
    if WORKSPACE.exists():
        shutil.rmtree(WORKSPACE)
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    comparison = bp.build_generated_host(
        lambda: build["files"]["program.c"],
        support_sources=(
            bp.BuildSource("p8_image_v1.c", bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE, build["files"]["p8_image_v1.c"].encode("utf-8")),
            bp.BuildSource("p8_runtime_support.c", bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE, build["files"]["p8_runtime_support.c"].encode("utf-8")),
            bp.BuildSource("p8_driver.c", bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE, build["files"]["p8_driver.c"].encode("utf-8")),
        ),
        config=bp.BuildConfig(fixture_id="p8-09-reference-equivalence", smoke_test=False, run_count=2),
        workspace=WORKSPACE,
        keep_workspace=True,
    )
    executable = WORKSPACE / "run1" / "program.exe"
    outputs = []
    for _ in range(NATIVE_RUNS):
        completed = subprocess.run([str(executable)], capture_output=True, timeout=600)
        if completed.returncode != 0 or completed.stderr:
            raise AssertionError("native execution failed")
        outputs.append(completed.stdout)
    if len(set(outputs)) != 1:
        raise AssertionError("native execution is not deterministic")
    return build, comparison, executable, outputs[0]


def main() -> int:
    try:
        data = FIXTURE_ELF.read_bytes()
        check("fixture:sha256", sha256_bytes(data) == FIXTURE_SHA256, sha256_bytes(data))

        reference_source = (ROOT / ".openrecomp-phase8" / "src" / "p8_reference_mips32_v1.py").read_text(encoding="utf-8")
        import_lines = [
            line.strip()
            for line in reference_source.splitlines()
            if line.strip().startswith(("import ", "from "))
        ]
        forbidden = [
            token for token in FORBIDDEN_REFERENCE_IMPORTS if any(token in line for line in import_lines)
        ]
        check("reference:independent-module", forbidden == [], ",".join(forbidden) or "none")
        check(
            "reference:no-recompilation-imports",
            not any(line.startswith(("import openrecomp", "from openrecomp")) for line in import_lines),
            json.dumps(import_lines),
        )

        build, comparison, executable, native_stdout = build_and_run_native()
        native = parse_native(native_stdout.decode("utf-8"))
        check("native:exit", native.get("failed") == "0" and native.get("error") == "", f"failed={native.get('failed')} error={native.get('error')!r}")

        loaded = reference.load_elf32(data)
        check("reference:loader-image-size", len(loaded.image) == 0x6710, hex(len(loaded.image)))
        check("reference:loader-objects", len(loaded.regions) == 4 and len(loaded.executable) == 1, f"{len(loaded.regions)}/{len(loaded.executable)}")
        check("reference:loader-entry", loaded.entry == 0x2490, hex(loaded.entry))
        run = reference.execute(loaded)
        check("reference:halted", run.halted and run.steps > 0, f"steps={run.steps}")
        observed = run.to_observables()
        check("reference:exit-status", observed["exit_status"] == "0x00000000", observed["exit_status"])
        check("reference:transcript", observed["transcript_text"] == "69c4e0d86a7b0430d8cdb78070b4c55a\n", observed["transcript_text"])

        # native record from the recorded P8-08 evidence (guards against drift)
        recorded = json.loads(P8_08_EVIDENCE.read_text(encoding="utf-8"))["observable"]
        check("recorded:p8-08-present", recorded["exit_status"] == "0x00000000", recorded["exit_status"])

        # field-by-field equivalence, no excluded observables
        fields = (
            ("exit_status", native.get("exit_status"), observed["exit_status"]),
            ("registers_digest", native.get("registers_digest"), observed["registers_digest"]),
            ("memory_digest", native.get("memory"), observed["memory_digest"]),
            ("transcript_len", native.get("transcript_len"), observed["transcript_len"]),
            ("transcript_digest", native.get("transcript"), observed["transcript_digest"]),
            ("reads", native.get("reads"), observed["reads"]),
            ("writes", native.get("writes"), observed["writes"]),
            ("host_calls", native.get("host_calls"), observed["host_calls"]),
            ("denied", native.get("denied"), observed["denied"]),
        )
        comparisons = {}
        for name, native_value, reference_value in fields:
            comparisons[name] = {"native": native_value, "reference": reference_value}
            check(f"equivalence:{name}", native_value == reference_value, f"{native_value!r} == {reference_value!r}")

        register_mismatches = []
        for index in range(32):
            native_value = native["registers"][index]
            reference_value = observed["registers"][f"r{index:02d}"]
            if native_value != reference_value:
                register_mismatches.append({"register": f"r{index:02d}", "native": native_value, "reference": reference_value})
        check("equivalence:registers", register_mismatches == [], json.dumps(register_mismatches))

        recorded_mismatches = []
        for name, _, reference_value in fields:
            recorded_value = {
                "exit_status": recorded["exit_status"],
                "registers_digest": recorded["registers_digest"],
                "memory_digest": recorded["memory_digest"],
                "transcript_len": recorded["transcript_len"],
                "transcript_digest": recorded["transcript_digest"],
                "reads": recorded["reads"],
                "writes": recorded["writes"],
                "host_calls": recorded["host_calls"],
                "denied": recorded["denied"],
            }[name]
            if recorded_value != reference_value:
                recorded_mismatches.append({"field": name, "recorded": recorded_value, "reference": reference_value})
        for index in range(32):
            recorded_value = recorded["registers"][f"r{index:02d}"]
            reference_value = observed["registers"][f"r{index:02d}"]
            if recorded_value != reference_value:
                recorded_mismatches.append({"register": f"r{index:02d}", "recorded": recorded_value, "reference": reference_value})
        check("equivalence:recorded-p8-08-match", recorded_mismatches == [], json.dumps(recorded_mismatches))
        check(
            "equivalence:no-excluded-observables",
            len(fields) == 9 and register_mismatches == [] and recorded_mismatches == [],
            "exit value, all registers, register digest, memory digest, transcript length/digest and every event count compared",
        )
        check("equivalence:native-executable", executable.is_file(), sha256_bytes(executable.read_bytes()))

        write_evidence(
            "reference_equivalence.json",
            {
                "stage": STAGE,
                "reference_version": reference.REFERENCE_VERSION,
                "fixture": {"sha256": FIXTURE_SHA256},
                "native": {
                    "emission_fingerprint": build["program_fingerprint"],
                    "executable_sha256": sha256_bytes(executable.read_bytes()),
                    "runs": NATIVE_RUNS,
                },
                "reference": {
                    "independent_module": ".openrecomp-phase8/src/p8_reference_mips32_v1.py",
                    "module_sha256": sha256_bytes(reference_source.encode("utf-8")),
                    "loader_image_size": len(loaded.image),
                    "steps": run.steps,
                    "observables": observed,
                },
                "comparisons": comparisons,
                "register_mismatches": register_mismatches,
                "recorded_mismatches": recorded_mismatches,
                "excluded_observables": [],
                "markers": {
                    "terminal": f"{TERMINAL_MARKER}={NOT_PROVEN}",
                    "general": f"{GENERAL_MARKER}={NOT_PROVEN}",
                },
            },
        )
    except Exception as exc:  # stable fail-closed boundary
        RESULTS.append({"check": "gate:exception", "status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"})

    status = "PASS" if all(item["status"] == "PASS" for item in RESULTS) else "FAIL"
    record = {
        "stage": STAGE,
        "stage_name": "Independent reference equivalence",
        "status": status,
        "tests": len(RESULTS),
        "passed": sum(1 for item in RESULTS if item["status"] == "PASS"),
        "failed": sum(1 for item in RESULTS if item["status"] != "PASS"),
        "checks": RESULTS,
        "failure": None if status == "PASS" else [item for item in RESULTS if item["status"] != "PASS"],
        "markers": {
            "stage": f"{STAGE_MARKER}={status}",
            "gate": f"{FEATURE_MARKER}={status} tests={len(RESULTS)}",
            "terminal": f"{TERMINAL_MARKER}={NOT_PROVEN}",
            "general": f"{GENERAL_MARKER}={NOT_PROVEN}",
        },
    }
    write_evidence("p8_09_tests.json", record)

    for item in RESULTS:
        if item["status"] != "PASS":
            print(f"FAIL: {item['check']} :: {item.get('detail', '')}")
    print(f"{STAGE_MARKER}={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(RESULTS)}")
    print(f"{TERMINAL_MARKER}={NOT_PROVEN}")
    print(f"{GENERAL_MARKER}={NOT_PROVEN}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
