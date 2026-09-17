#!/usr/bin/env python3
"""OpenRecomp Phase-3 native build + generic runtime execution gate (P3-08).

P3-08 builds the P3-07 generated host translation with the frozen Phase-2
deterministic build pipeline, executes the resulting native program through the
P2-08 generic runtime ABI boundary and records the deterministic observable.

The deterministic gate:

* verifies source integrity: the frozen root ``SOURCE_SHA256SUMS.txt`` is
  unchanged and every entry still hashes, and the Phase-3
  ``.openrecomp-phase3/SOURCE_SHA256SUMS.txt`` manifest registers and verifies
  the Phase-3 source/gate files (grown additively to this stage's set);
* re-emits the host program/support from the frozen inputs and pins the exact
  P3-07 fingerprints, so P3-08 executes the audited translation;
* builds the program with ``openrecomp.build_pipeline`` in isolated run
  directories and proves the build is byte-reproducible (source, objects,
  executable, manifest) with the recorded toolchain identity and no path or
  process identity leakage;
* executes the native program repeatedly, requires byte-identical stdout and
  records the deterministic observable (exit status, step count, PC, HI/LO,
  UART stream, FNV-1a 64 state digest, failure state);
* independently checks CoreMark's own validation contract: the UART stream must
  contain ``Correct operation validated`` and the published CoreMark validation
  CRC values (``seedcrc 0xe9f5``, ``crclist 0xe714``, ``crcmatrix 0x1fd7``,
  ``crcstate 0x8e3a``, ``crcfinal 0xd340``);
* builds and runs tiny synthetic programs to prove the runtime fail-closed
  paths at run time (divide by zero, taken trap, unaligned indirect target,
  out-of-image memory access);
* captures the build manifests and execution captures as evidence.

On success it emits::

    OPENRECOMP_P3_08=PASS
    OPENRECOMP_PHASE3_NATIVE_RUNTIME_V1=PASS tests=<count>

Any failed invariant fails closed and emits ``OPENRECOMP_P3_08=FAIL``.

Usage:

    python tools/test_phase3_native_runtime_v1.py
    python tools/test_phase3_native_runtime_v1.py --workspace .openrecomp-phase3/build/P3-08/native
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / ".openrecomp-phase3" / "src"
for candidate in (str(ROOT), str(SRC_DIR)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from p3_code_frontier_v1 import analyze  # noqa: E402
from p3_decode_mips32_v1 import classify  # noqa: E402
from p3_elf_image_v1 import evidence_json_bytes, ingest, sha256_bytes  # noqa: E402
from p3_host_emit_v1 import emit_program  # noqa: E402
from p3_static_data_v1 import MappedRegion, StaticDataModel, build_static_data_model  # noqa: E402
from p3_target_mips32_v1 import MIPS32_O32  # noqa: E402
from openrecomp import build_pipeline as bp  # noqa: E402

EVIDENCE_ROOT = ROOT / ".openrecomp-phase3" / "evidence"
DEFAULT_EVIDENCE_DIR = EVIDENCE_ROOT / "P3-08"
P3_07_EVIDENCE = EVIDENCE_ROOT / "P3-07"

STAGE = "P3-08"
STAGE_MARKER = "OPENRECOMP_P3_08"
FEATURE_MARKER = "OPENRECOMP_PHASE3_NATIVE_RUNTIME_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF"

P3_SOURCE_MANIFEST = ROOT / ".openrecomp-phase3" / "SOURCE_SHA256SUMS.txt"
P3_SOURCE_FILES = (
    ".openrecomp-phase3/src/p3_code_frontier_v1.py",
    ".openrecomp-phase3/src/p3_decode_mips32_v1.py",
    ".openrecomp-phase3/src/p3_elf_image_v1.py",
    ".openrecomp-phase3/src/p3_host_emit_v1.py",
    ".openrecomp-phase3/src/p3_package_v1.py",
    ".openrecomp-phase3/src/p3_reference_mips32_v1.py",
    ".openrecomp-phase3/src/p3_semantics_mips32_v1.py",
    ".openrecomp-phase3/src/p3_static_data_v1.py",
    ".openrecomp-phase3/src/p3_structure_v1.py",
    ".openrecomp-phase3/src/p3_target_mips32_v1.py",
    "tools/test_phase3_boundary_v1.py",
    "tools/test_phase3_coremark_fixture_v1.py",
    "tools/test_phase3_decode_frontier_v1.py",
    "tools/test_phase3_elf_ingestion_v1.py",
    "tools/test_phase3_evidence_index_v1.py",
    "tools/test_phase3_host_emit_v1.py",
    "tools/test_phase3_native_runtime_v1.py",
    "tools/test_phase3_package_regression_v1.py",
    "tools/test_phase3_reachable_semantics_v1.py",
    "tools/test_phase3_reference_equivalence_v1.py",
    "tools/test_phase3_static_data_v1.py",
    "tools/test_phase3_structure_v1.py",
    "tools/test_phase3_whole_regression_v1.py",
)
ROOT_MANIFEST = ROOT / "SOURCE_SHA256SUMS.txt"
ROOT_MANIFEST_SHA256 = "76f77bbc97780afe9c2b41a0cb89b5323ab22450c4b2a368dd03fb4d7bbe1095"
ROOT_MANIFEST_ENTRIES = 134

DEFAULT_ELF = (
    ROOT / ".openrecomp-phase3" / "build" / "P3-01" / "candidate-a"
    / "coremark_mips32_O1.elf"
)
DEFAULT_WORKSPACE = ROOT / ".openrecomp-phase3" / "build" / "P3-08" / "native"
ELF_SHA256 = "16a0a0aa0f62344d8c0f309b755450f09c330e7c5a7c355785662d7a141f7669"
ELF_SIZE = 31184
TEXT_VADDR = 0x1000
TEXT_SIZE = 13948
ENTRY = 0x4650

EXPECTED_PROGRAM_FINGERPRINT = (
    "5199e2f0a11974847966bd7ea6b855e0147c6e762d002ede3f14bc3ee8d9649a"
)
EXPECTED_SUPPORT_FINGERPRINT = (
    "c5c69054cbbcd4e6ea9259f2e3d80e4bfada6fc12fec1cfe3fe9224b9f861580"
)
EXPECTED_OBSERVABLE = {
    "exit_status": "0",
    "pc": "0x00004564",
    "hi": "0x0000000d",
    "lo": "0x00000000",
    "uart_bytes": "499",
    "state_fnv1a64": "0x78651c29dd149ab1",
    "failed": "0",
    "failure": "",
}
EXPECTED_COREMARK_LINES = (
    "CoreMark Size    : 666",
    "Total ticks      : 10000",
    "Iterations       : 1000",
    "seedcrc          : 0xe9f5",
    "[0]crclist       : 0xe714",
    "[0]crcmatrix     : 0x1fd7",
    "[0]crcstate      : 0x8e3a",
    "[0]crcfinal      : 0xd340",
    "Correct operation validated.",
)
EXPECTED_REPLAY_COUNT = 3

SOURCE_INTEGRITY = "source_integrity.txt"
PIN_JSON = "emission_pin.json"
BUILD_JSON = "build_report.json"
BUILD_RUN_1 = "build_run_1.txt"
BUILD_RUN_2 = "build_run_2.txt"
NATIVE_JSON = "native_execution.json"
NATIVE_TXT = "native_execution.txt"
NEGATIVES_JSON = "runtime_negatives.json"
DETERMINISM = "determinism.json"
RESULT_JSON = "RESULT.json"

CLAIM_BOUNDARY = (
    "P3-08 proves only that the P3-07 generated translation builds into a "
    "byte-reproducible native program and executes deterministically through "
    "the P2-08 generic runtime ABI, with CoreMark's own validation CRCs and "
    "fail-closed runtime boundaries demonstrated. It does not yet prove "
    "equivalence against an independent MIPS32 reference (P3-09) and claims no "
    "arbitrary MIPS32, PS1 or PS2 compatibility."
)

RESULTS: list[dict[str, str]] = []
FINDINGS: dict[str, Any] = {}
ARTIFACTS: dict[str, bytes] = {}
EVIDENCE_DIR = DEFAULT_EVIDENCE_DIR
WORKSPACE = DEFAULT_WORKSPACE


def check(label: str, condition: bool) -> None:
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL"})
        print(f"FAIL: {label}", flush=True)
        raise AssertionError(f"{label}: condition failed")
    RESULTS.append({"check": label, "status": "PASS"})
    print(f"PASS: {label}", flush=True)


def banner(name: str) -> None:
    print(f"\n--- {name} ---", flush=True)


def parse_manifest(path: pathlib.Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        if " *" not in line:
            raise ValueError(f"unparsable manifest line: {line[:80]}")
        digest, relative = line.split(" *", 1)
        if relative in entries:
            raise ValueError(f"duplicate manifest entry: {relative}")
        entries[relative] = digest
    return entries


def audit_source_integrity() -> None:
    check("source:root-manifest-exists", ROOT_MANIFEST.is_file())
    root_digest = sha256_bytes(ROOT_MANIFEST.read_bytes())
    check("source:root-manifest-frozen-sha256", root_digest == ROOT_MANIFEST_SHA256)
    root_entries = parse_manifest(ROOT_MANIFEST)
    check("source:root-manifest-entry-count", len(root_entries) == ROOT_MANIFEST_ENTRIES)
    check("source:root-manifest-entries-verified", not [
        relative for relative, digest in sorted(root_entries.items())
        if not (ROOT / relative).is_file()
        or sha256_bytes((ROOT / relative).read_bytes()) != digest])
    check("source:phase3-manifest-exists", P3_SOURCE_MANIFEST.is_file())
    phase3_digest = sha256_bytes(P3_SOURCE_MANIFEST.read_bytes())
    phase3_entries = parse_manifest(P3_SOURCE_MANIFEST)
    check("source:phase3-manifest-entry-set",
          tuple(sorted(phase3_entries)) == tuple(sorted(P3_SOURCE_FILES)))
    check("source:phase3-manifest-entries-verified", not [
        relative for relative, digest in sorted(phase3_entries.items())
        if not (ROOT / relative).is_file()
        or sha256_bytes((ROOT / relative).read_bytes()) != digest])
    lines = [
        f"PHASE3_SOURCE_MANIFEST={P3_SOURCE_MANIFEST.relative_to(ROOT).as_posix()}",
        f"PHASE3_SOURCE_MANIFEST_SHA256={phase3_digest}",
        f"PHASE3_SOURCE_ENTRIES={len(phase3_entries)}",
    ]
    lines += [f"{digest} *{relative}" for relative, digest in sorted(phase3_entries.items())]
    lines += [
        "PHASE3_SOURCE_INTEGRITY=PASS",
        f"ROOT_SOURCE_MANIFEST={ROOT_MANIFEST.name}",
        f"ROOT_SOURCE_MANIFEST_SHA256={root_digest}",
        f"ROOT_SOURCE_MANIFEST_ENTRIES={len(root_entries)}",
        "ROOT_SOURCE_INTEGRITY=PASS",
    ]
    ARTIFACTS[SOURCE_INTEGRITY] = ("\n".join(lines) + "\n").encode("utf-8")
    FINDINGS["source_integrity"] = {
        "root_manifest_sha256": root_digest,
        "phase3_manifest_sha256": phase3_digest,
        "phase3_manifest_entries": len(phase3_entries),
    }


def reemit(elf_path: pathlib.Path):
    check("fixture:exists", elf_path.is_file())
    data = elf_path.read_bytes()
    check("fixture:sha256", sha256_bytes(data) == ELF_SHA256)
    check("fixture:size", len(data) == ELF_SIZE)
    ingested = ingest(data, MIPS32_O32)
    analysis = analyze(ingested.image.read_u32, TEXT_VADDR, TEXT_VADDR + TEXT_SIZE, ENTRY)
    model = build_static_data_model(ingested)
    program = emit_program(analysis, model, source_sha256=ELF_SHA256)
    pinned = json.loads((P3_07_EVIDENCE / "RESULT.json").read_text(encoding="utf-8"))
    check("pin:program-fingerprint",
          program.fingerprint == pinned["findings"]["emission"]["program_fingerprint"])
    check("pin:support-fingerprint",
          program.support_fingerprint == pinned["findings"]["emission"]["support_fingerprint"])
    check("pin:program-constant", program.fingerprint == EXPECTED_PROGRAM_FINGERPRINT)
    check("pin:support-constant", program.support_fingerprint == EXPECTED_SUPPORT_FINGERPRINT)
    check("pin:evidence-program-sha",
          sha256_bytes((P3_07_EVIDENCE / "coremark_program.c").read_bytes())
          == sha256_bytes(program.program_text.encode("utf-8")))
    payload = {
        "stage": STAGE,
        "program_fingerprint": program.fingerprint,
        "support_fingerprint": program.support_fingerprint,
        "p3_07_program_fingerprint": pinned["findings"]["emission"]["program_fingerprint"],
        "p3_07_support_fingerprint": pinned["findings"]["emission"]["support_fingerprint"],
        "case_count": program.case_count,
        "source": "re-emitted from the frozen P3-03/P3-05/P3-06 inputs",
    }
    ARTIFACTS[PIN_JSON] = evidence_json_bytes(payload)
    FINDINGS["emission_pin"] = payload
    return data, program


def prepare_workspace() -> None:
    for name in ("run1", "run2"):
        target = WORKSPACE / name
        if target.exists():
            shutil.rmtree(target)
    WORKSPACE.mkdir(parents=True, exist_ok=True)


def run_build(program) -> Any:
    config = bp.BuildConfig(
        fixture_id="p3-08-coremark-native-runtime",
        smoke_test=False,
        run_count=2,
    )
    comparison = bp.build_generated_host(
        lambda: program.program_text,
        support_sources=(
            bp.BuildSource("coremark_support.c",
                           bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE,
                           program.support_text.encode("utf-8")),
        ),
        config=config,
        workspace=WORKSPACE,
        keep_workspace=True,
    )
    check("build:status-ok",
          all(run.manifest.build_status is bp.BuildStatus.OK for run in comparison.runs))
    check("build:classification",
          comparison.classification is bp.BuildReproducibility.EXECUTABLE_REPRODUCIBLE)
    check("build:source-reproducible", comparison.source_reproducible)
    check("build:manifest-reproducible", comparison.manifest_reproducible)
    check("build:object-reproducible", comparison.object_reproducible is True)
    check("build:executable-reproducible", comparison.executable_reproducible is True)
    check("build:toolchain-identity", all(
        run.manifest.toolchain.compiler.identity == "clang-cl.exe"
        and run.manifest.toolchain.linker.identity == "lld-link.exe"
        and run.manifest.toolchain.compiler.version
        and run.manifest.toolchain.linker.version
        for run in comparison.runs))
    check("build:brepro-flags", all(
        "/Brepro" in command for run in comparison.runs
        for command in run.manifest.compile_commands))
    check("build:manifest-deterministic",
          comparison.runs[0].manifest.serialize() == comparison.runs[1].manifest.serialize())
    manifest_text = comparison.runs[0].manifest.serialize().decode("utf-8")
    check("build:no-host-path-leak",
          str(ROOT) not in manifest_text and str(WORKSPACE) not in manifest_text)
    check("build:no-identity-leak", (
        not os.environ.get("USERNAME") or os.environ["USERNAME"] not in manifest_text)
        and (not os.environ.get("COMPUTERNAME")
             or os.environ["COMPUTERNAME"] not in manifest_text))
    payload = {
        "stage": STAGE,
        "classification": comparison.classification.value,
        "source_reproducible": comparison.source_reproducible,
        "object_reproducible": comparison.object_reproducible,
        "executable_reproducible": comparison.executable_reproducible,
        "manifest_reproducible": comparison.manifest_reproducible,
        "runs": [{
            "index": run.index,
            "build_status": run.manifest.build_status.value,
            "manifest_sha256": run.manifest.fingerprint(),
            "toolchain": {
                "compiler": run.manifest.toolchain.compiler.to_document(),
                "linker": run.manifest.toolchain.linker.to_document(),
            },
            "inputs": [{"name": item.name, "kind": item.kind.value, "sha256": item.sha256}
                       for item in run.manifest.inputs],
            "outputs": [{"name": item.name, "kind": item.kind.value, "sha256": item.sha256}
                        for item in run.manifest.outputs],
            "compile_commands": [list(command) for command in run.manifest.compile_commands],
            "link_command": list(run.manifest.link_command),
        } for run in comparison.runs],
    }
    ARTIFACTS[BUILD_JSON] = evidence_json_bytes(payload)
    for index, run in enumerate(comparison.runs):
        lines = [
            f"P3-08 deterministic build run {index + 1}",
            "=" * 34,
            f"build_status: {run.manifest.build_status.value}",
            "inputs:",
        ]
        for item in run.manifest.inputs:
            lines.append(f"  {item.kind.value} {item.name} {item.sha256}")
        lines.append("outputs:")
        for item in run.manifest.outputs:
            lines.append(f"  {item.kind.value} {item.name} {item.sha256}  sha256={item.sha256}")
        lines.append(f"manifest_sha256: {run.manifest.fingerprint()}")
        lines.append("")
        ARTIFACTS[BUILD_RUN_1 if index == 0 else BUILD_RUN_2] = (
            "\n".join(lines)).encode("utf-8")
    FINDINGS["build"] = {
        "classification": comparison.classification.value,
        "executable_reproducible": comparison.executable_reproducible,
        "manifest_sha256": comparison.runs[0].manifest.fingerprint(),
        "artifacts": [{"name": item.name, "sha256": item.sha256}
                      for item in comparison.runs[0].manifest.outputs],
    }
    return comparison


def parse_observable(stdout: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            if key in ("exit_status", "steps", "pc", "hi", "lo", "uart_bytes",
                       "uart_hex", "state_fnv1a64", "failed", "failure"):
                fields[key] = value
    return fields


def run_native(comparison) -> dict[str, Any]:
    executable = WORKSPACE / "run1" / "program.exe"
    check("native:executable-exists", executable.is_file())
    exe_sha = sha256_bytes(executable.read_bytes())
    claimed = comparison.runs[0].manifest.artifact_map(bp.BuildArtifactKind.EXECUTABLE)
    check("native:executable-hash-matches-manifest", claimed.get("program.exe") == exe_sha)
    outputs = []
    for _ in range(EXPECTED_REPLAY_COUNT):
        ran = subprocess.run([str(executable)], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=3600)
        outputs.append((ran.stdout or "", ran.returncode))
    check("native:returncode-zero", all(rc == 0 for _, rc in outputs))
    check("native:replay-identical", len({text for text, _ in outputs}) == 1)
    stdout = outputs[0][0]
    observable = parse_observable(stdout)
    for key, expected in EXPECTED_OBSERVABLE.items():
        check(f"native:observable:{key}", observable.get(key) == expected)
    check("native:steps-positive", int(observable.get("steps", "0")) > 0)
    check("native:state-hash-format",
          re.fullmatch(r"0x[0-9a-f]{16}", observable.get("state_fnv1a64", "")) is not None)
    uart = bytes.fromhex(observable.get("uart_hex", ""))
    check("native:uart-length",
          len(uart) == int(observable.get("uart_bytes", "-1")))
    text = uart.decode("ascii", errors="strict")
    for marker in EXPECTED_COREMARK_LINES:
        check(f"native:coremark-line:{marker.split(':')[0]}", marker in text)
    check("native:coremark-validated", "Correct operation validated." in text)
    check("native:no-failure", observable.get("failure") == ""
          and observable.get("failed") == "0")

    payload = {
        "stage": STAGE,
        "executable_sha256": exe_sha,
        "replays": EXPECTED_REPLAY_COUNT,
        "stdout_sha256": sha256_bytes(stdout.encode("utf-8")),
        "observable": observable,
        "coremark_lines": list(EXPECTED_COREMARK_LINES),
        "uart_text": text,
    }
    ARTIFACTS[NATIVE_JSON] = evidence_json_bytes(payload)
    ARTIFACTS[NATIVE_TXT] = (
        "P3-08 native execution\n"
        "======================\n"
        f"executable sha256: {exe_sha}\n"
        f"replays: {EXPECTED_REPLAY_COUNT}\n"
        f"stdout sha256: {payload['stdout_sha256']}\n"
        "stdout:\n" + stdout + "\n"
    ).encode("utf-8")
    FINDINGS["native"] = {
        "executable_sha256": exe_sha,
        "stdout_sha256": payload["stdout_sha256"],
        "observable": observable,
        "uart_text_sha256": sha256_bytes(text.encode("ascii")),
    }
    return payload


def tiny_model() -> StaticDataModel:
    return StaticDataModel((), (), regions=(MappedRegion(0x0, 0x1000, "rw-"),))


def tiny_program(words: dict[int, int], entry: int = 0x1000):
    records = [classify(address, word) for address, word in sorted(words.items())]
    analysis = {
        "region": {"start": entry, "end": max(words) + 4, "words": len(words)},
        "entry": entry,
        "records": records,
        "reachable_addresses": sorted(words),
        "unreachable_addresses": [],
        "delay_slots": [],
        "control_flow": {},
        "unresolved": [],
        "exception_sites": [],
        "diagnostics": {},
    }
    return emit_program(analysis, tiny_model(), source_sha256=ELF_SHA256)


def build_and_run_tiny(name: str, program, workspace: pathlib.Path) -> str:
    config = bp.BuildConfig(
        fixture_id=f"p3-08-negative-{name}",
        smoke_test=False,
        run_count=2,
        reproducible=False,
    )
    comparison = bp.build_generated_host(
        lambda: program.program_text,
        support_sources=(
            bp.BuildSource("coremark_support.c",
                           bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE,
                           program.support_text.encode("utf-8")),
        ),
        config=config,
        workspace=workspace,
        keep_workspace=True,
    )
    if comparison.runs[0].manifest.build_status is not bp.BuildStatus.OK:
        return f"BUILD_FAILED:{name}"
    executable = workspace / "run1" / "program.exe"
    ran = subprocess.run([str(executable)], capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=600)
    return ran.stdout or ""


def audit_runtime_negatives() -> None:
    base = WORKSPACE.parent / "negatives"
    cases = [
        ("div-by-zero", {0x1000: 0x0085001B}, "divide by zero"),
        ("teq-trap", {0x1000: (4 << 21) | (5 << 16) | 0x34}, "teq trap code=0x0"),
        ("unaligned-jr", {0x1000: 0x24040002, 0x1004: 0x00800008, 0x1008: 0x00000000},
         "unaligned indirect jump target"),
        ("memory-out-of-range", {0x1000: 0x3C042000, 0x1004: 0xAC850000},
         "MEMORY_OUT_OF_RANGE"),
    ]
    rows = []
    for name, words, marker in cases:
        workspace = base / name
        if workspace.exists():
            shutil.rmtree(workspace)
        workspace.mkdir(parents=True)
        program = tiny_program(words)
        stdout = build_and_run_tiny(name, program, workspace)
        observable = parse_observable(stdout)
        status = "PASS" if (observable.get("failed") == "1"
                            and observable.get("failure") == marker) else "FAIL"
        rows.append({
            "fixture": name,
            "expected_failure": marker,
            "observed_failure": observable.get("failure"),
            "observed_failed": observable.get("failed"),
            "status": status,
        })
    failures = [row for row in rows if row["status"] != "PASS"]
    for row in failures:
        print(f"NEGATIVE-FAILURE: {row}", flush=True)
    check("negatives:no-failures", not failures)
    check("negatives:count", len(rows) == len(cases))
    ARTIFACTS[NEGATIVES_JSON] = evidence_json_bytes(
        {"stage": STAGE, "cases": rows, "failed": len(failures)})
    FINDINGS["runtime_negatives"] = rows


def audit_determinism(data: bytes) -> None:
    artifact_hashes = {name: sha256_bytes(payload) for name, payload in sorted(ARTIFACTS.items())}
    record = {
        "source_sha256": sha256_bytes(data),
        "artifact_sha256": artifact_hashes,
    }
    ARTIFACTS[DETERMINISM] = evidence_json_bytes(record)
    FINDINGS["determinism"] = record
    check("determinism:artifact-hashes-recorded", bool(artifact_hashes))


def write_evidence() -> dict[str, str]:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    hashes: dict[str, str] = {}
    for name, payload in sorted(ARTIFACTS.items()):
        (EVIDENCE_DIR / name).write_bytes(payload)
        hashes[name] = sha256_bytes(payload)
    return hashes


def main() -> int:
    parser = argparse.ArgumentParser(description="P3-08 native runtime gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase3/evidence/P3-08")
    parser.add_argument("--workspace", type=str,
                        default=os.environ.get("OPENRECOMP_P3_08_WORKSPACE",
                                               str(DEFAULT_WORKSPACE)))
    parser.add_argument("--elf", type=str,
                        default=os.environ.get("OPENRECOMP_P3_ELF", str(DEFAULT_ELF)))
    args = parser.parse_args()

    global EVIDENCE_DIR, WORKSPACE, RESULTS, FINDINGS, ARTIFACTS
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    WORKSPACE = pathlib.Path(args.workspace)
    if not WORKSPACE.is_absolute():
        WORKSPACE = (ROOT / WORKSPACE).resolve()
    RESULTS = []
    FINDINGS = {}
    ARTIFACTS = {}
    elf_path = pathlib.Path(args.elf)
    if not elf_path.is_absolute():
        elf_path = (ROOT / elf_path).resolve()

    print("=== P3-08 Native Build + Runtime Gate ===", flush=True)
    failure: str | None = None
    status = "PASS"
    evidence_files: dict[str, str] = {}
    try:
        banner("source_integrity")
        audit_source_integrity()
        banner("re-emission pin")
        data, program = reemit(elf_path)
        banner("build")
        prepare_workspace()
        comparison = run_build(program)
        banner("native execution")
        run_native(comparison)
        banner("runtime negatives")
        audit_runtime_negatives()
        banner("determinism")
        audit_determinism(data)
        evidence_files = write_evidence()
    except Exception as exc:  # noqa: BLE001 - fail closed without traceback
        failure = f"{type(exc).__name__}: {exc}"
        status = "FAIL"

    passed = sum(1 for item in RESULTS if item["status"] == "PASS")
    failed = sum(1 for item in RESULTS if item["status"] == "FAIL") + (1 if failure else 0)
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
        },
        "claim_boundary": CLAIM_BOUNDARY,
        "checks": sorted(RESULTS, key=lambda item: item["check"]),
        "findings": FINDINGS,
        "evidence_files": evidence_files,
        "failure": failure,
    }
    payload = evidence_json_bytes(result)
    (EVIDENCE_DIR / RESULT_JSON).write_bytes(payload)

    print("\n=== RESULT ===")
    if status == "PASS":
        print(f"{STAGE_MARKER}=PASS")
        print(f"{FEATURE_MARKER}=PASS tests={passed}")
        print(f"{TERMINAL_MARKER}=NOT_PROVEN")
        return 0
    print(f"{STAGE_MARKER}=FAIL ({failure})")
    print(f"{FEATURE_MARKER}=FAIL")
    print(f"{TERMINAL_MARKER}=NOT_PROVEN")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
