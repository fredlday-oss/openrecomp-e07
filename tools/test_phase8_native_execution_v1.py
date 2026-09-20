#!/usr/bin/env python3
"""OpenRecomp Phase-8 deterministic native execution gate (P8-08).

P8-08 executes the generated native program and defines the bounded
observable record:

* exit value (`$v0` at the return boundary);
* the full guest register file at the agreed boundary plus its digest;
* the guest memory digest;
* the output/service transcript (length and digest);
* memory read/write, host-call and denied-access event counts.

The official gate builds the emission set through the existing deterministic
build pipeline, executes the native program three times, requires
byte-identical output, verifies the record's internal consistency, and checks
the fixture's known-answer output transcript against an independently
computed FNV-1a 64 digest of the FIPS-197 AES-128 ciphertext hex line.

Full native-vs-independent-reference equivalence is P8-09.

On success it emits::

    OPENRECOMP_P8_08=PASS
    OPENRECOMP_PHASE8_NATIVE_EXECUTION_V1=PASS tests=<count>
    OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase8_native_execution_v1.py
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
import p8_structure_v1 as structure_bridge  # noqa: E402
from openrecomp import build_pipeline as bp  # noqa: E402
from openrecomp.program_model import ProgramSource  # noqa: E402

EVIDENCE_DIR = ROOT / ".openrecomp-phase8" / "evidence" / "P8-08"
WORKSPACE = ROOT / ".openrecomp-phase8" / "build" / "P8-08"

STAGE = "P8-08"
STAGE_MARKER = "OPENRECOMP_P8_08"
FEATURE_MARKER = "OPENRECOMP_PHASE8_NATIVE_EXECUTION_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY"
NOT_PROVEN = "NOT_PROVEN"

FIXTURE_ELF = ROOT / ".openrecomp-phase8" / "build" / "P8-01" / "candidate-a" / "p8_aes128_mips32_O1.elf"
FIXTURE_SHA256 = "0a90f47754f6331b868ec09ad23c451fc2c73925a43897fa62a696b0d40dde65"
EXPECTED_PROGRAM_FINGERPRINT = "6a957bd1639cebf8b702725682b3423accf0e01191a5fa73e9dc9849c9ff3294"
EXPECTED_TRANSCRIPT = b"69c4e0d86a7b0430d8cdb78070b4c55a\n"
SUPPORT_SOURCE = ROOT / ".openrecomp-phase8" / "runtime" / "p8_runtime_support.c"
DRIVER_SOURCE = ROOT / ".openrecomp-phase8" / "runtime" / "p8_observable_driver.c"
EXECUTIONS = 3

RESULTS: list[dict[str, str]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL", "detail": detail})
        raise AssertionError(f"{label}: condition failed ({detail})")
    RESULTS.append({"check": label, "status": "PASS", "detail": detail})
    print(f"PASS: {label}")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fnv1a64(data: bytes) -> int:
    value = 0xCBF29CE484222325
    for byte in data:
        value ^= byte
        value = (value * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return value


def evidence_json(payload: object) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_evidence(name: str, payload: object) -> None:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    (EVIDENCE_DIR / name).write_bytes(evidence_json(payload))


def build_emission():
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
    return emission.build_build_set(
        structure,
        contract,
        image,
        SUPPORT_SOURCE.read_text(encoding="utf-8"),
        DRIVER_SOURCE.read_text(encoding="utf-8"),
        FIXTURE_SHA256,
    )


def parse_record(stdout: str) -> dict:
    record: dict = {"registers": {}}
    for line in stdout.splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.startswith("r") and len(key) == 3 and key[1:].isdigit():
            record["registers"][int(key[1:])] = int(value, 16)
        elif key == "registers":
            record["registers_digest"] = value
        elif key in ("transcript_len", "reads", "writes", "host_calls", "denied"):
            record[key] = int(value)
        else:
            record[key] = value
    return record


def main() -> int:
    try:
        data = FIXTURE_ELF.read_bytes()
        check("fixture:sha256", sha256_bytes(data) == FIXTURE_SHA256, sha256_bytes(data))
        build = build_emission()
        check("emission:program-fingerprint", build["program_fingerprint"] == EXPECTED_PROGRAM_FINGERPRINT, build["program_fingerprint"])

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
            config=bp.BuildConfig(fixture_id="p8-08-mips32-native-execution", smoke_test=False, run_count=2),
            workspace=WORKSPACE,
            keep_workspace=True,
        )
        check("build:status-ok", all(run.manifest.build_status is bp.BuildStatus.OK for run in comparison.runs), "ok")
        check("build:executable-reproducible", comparison.classification is bp.BuildReproducibility.EXECUTABLE_REPRODUCIBLE, comparison.classification.value)
        executable = WORKSPACE / "run1" / "program.exe"
        check("build:executable-exists", executable.is_file(), str(executable.name))

        outputs: list[bytes] = []
        parsed: list[dict] = []
        for index in range(EXECUTIONS):
            completed = subprocess.run(
                [str(executable)],
                capture_output=True,
                timeout=600,
            )
            check(f"execution:{index + 1}:exit", completed.returncode == 0, str(completed.returncode))
            check(f"execution:{index + 1}:stderr-empty", completed.stderr == b"", completed.stderr[:120].decode("ascii", "replace"))
            outputs.append(completed.stdout)
            parsed.append(parse_record(completed.stdout.decode("utf-8")))
        check("execution:byte-identical", len(set(outputs)) == 1, sha256_bytes(outputs[0]))

        record = parsed[0]
        check("observable:fixture", record.get("fixture") == FIXTURE_SHA256, str(record.get("fixture")))
        check("observable:failed", record.get("failed") == "0", str(record.get("failed")))
        check("observable:error-empty", record.get("error") == "", repr(record.get("error")))
        check("observable:exit-status", record.get("exit_status") == "0x00000000", str(record.get("exit_status")))
        check("observable:register-count", len(record["registers"]) == 32, str(len(record["registers"])))
        check("observable:zero-register", record["registers"][0] == 0, hex(record["registers"][0]))

        expected_transcript_digest = fnv1a64(EXPECTED_TRANSCRIPT)
        check("observable:transcript-length", record.get("transcript_len") == len(EXPECTED_TRANSCRIPT), str(record.get("transcript_len")))
        check(
            "observable:transcript-digest",
            record.get("transcript") == f"0x{expected_transcript_digest:016x}",
            str(record.get("transcript")),
        )
        check("observable:host-calls-match-transcript", record.get("host_calls") == record.get("transcript_len"), f"{record.get('host_calls')} vs {record.get('transcript_len')}")
        check("observable:no-denied-accesses", record.get("denied") == 0, str(record.get("denied")))
        check("observable:reads-positive", isinstance(record.get("reads"), int) and record["reads"] > 0, str(record.get("reads")))
        check("observable:writes-positive", isinstance(record.get("writes"), int) and record["writes"] > 0, str(record.get("writes")))

        registers_digest = 0xCBF29CE484222325
        for index in range(32):
            value = record["registers"][index] & 0xFFFFFFFF
            for byte in range(4):
                registers_digest ^= (value >> (8 * byte)) & 0xFF
                registers_digest = (registers_digest * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
        check(
            "observable:register-digest-consistent",
            record.get("registers_digest") == f"0x{registers_digest:016x}",
            str(record.get("registers_digest")),
        )
        check("observable:memory-digest-present", isinstance(record.get("memory"), str) and record["memory"].startswith("0x") and len(record["memory"]) == 18, str(record.get("memory")))

        write_evidence(
            "native_execution.json",
            {
                "stage": STAGE,
                "fixture": {"sha256": FIXTURE_SHA256},
                "emission": emission.emission_document(build),
                "build": {
                    "classification": comparison.classification.value,
                    "executable_sha256": sha256_bytes(executable.read_bytes()),
                    "executable_bytes": len(executable.read_bytes()),
                },
                "executions": [
                    {
                        "index": index + 1,
                        "stdout_sha256": sha256_bytes(output),
                        "stdout_bytes": len(output),
                    }
                    for index, output in enumerate(outputs)
                ],
                "observable": {
                    "exit_status": record.get("exit_status"),
                    "failed": record.get("failed"),
                    "error": record.get("error"),
                    "registers": {f"r{index:02d}": f"0x{record['registers'][index]:08x}" for index in range(32)},
                    "registers_digest": record.get("registers_digest"),
                    "memory_digest": record.get("memory"),
                    "transcript_len": record.get("transcript_len"),
                    "transcript_digest": record.get("transcript"),
                    "expected_transcript_text": EXPECTED_TRANSCRIPT.decode("ascii").rstrip("\n"),
                    "reads": record.get("reads"),
                    "writes": record.get("writes"),
                    "host_calls": record.get("host_calls"),
                    "denied": record.get("denied"),
                },
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
        "stage_name": "Deterministic native execution",
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
    write_evidence("p8_08_tests.json", record)

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
