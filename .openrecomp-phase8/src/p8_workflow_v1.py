#!/usr/bin/env python3
"""OpenRecomp Phase-8 reusable real-MIPS32 ELF-to-native workflow.

Deterministic pipeline for the proven bounded path:

    ELF -> classification -> analysis -> translation -> host generation
        -> native build -> execution -> result evidence

Unsupported cases fail closed with an explicit, stable category:

    UNSUPPORTED_ELF_CONTAINER
    UNSUPPORTED_ISA_SEMANTIC
    UNSUPPORTED_ABI_REQUIREMENT
    UNRESOLVED_INDIRECT_CONTROL_FLOW
    UNSUPPORTED_MEMORY_RUNTIME
    TOOLCHAIN_UNAVAILABLE
    BUILD_FAILURE
    EXECUTION_FAILURE
    REFERENCE_UNAVAILABLE
    REFERENCE_MISMATCH
    INPUT_UNREADABLE

The workflow never guesses a target, never treats data as code and never
widens compatibility silently; it reuses the frozen Phase-8 modules.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import subprocess
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]

import adapters.mips32 as mips32_adapter  # noqa: E402
import p3_code_frontier_v1 as frontier  # noqa: E402
import p3_elf_image_v1 as elf  # noqa: E402
import p3_target_mips32_v1 as target  # noqa: E402
import p8_emission_v1 as emission  # noqa: E402
import p8_memory_contract_v1 as contract_v1  # noqa: E402
import p8_mips32_semantics_v1 as semantics  # noqa: E402
import p8_reference_mips32_v1 as reference  # noqa: E402
import p8_structure_v1 as structure_bridge  # noqa: E402
from openrecomp import build_pipeline as bp  # noqa: E402
from openrecomp.host_emitter import HostEmitterError  # noqa: E402
from openrecomp.program_model import ProgramSource  # noqa: E402

WORKFLOW_VERSION = "1.0.0"

OUTCOME_COMPLETED = "COMPLETED"
OUTCOME_FAIL_CLOSED = "FAIL_CLOSED"

SUPPORT_SOURCE = ROOT / ".openrecomp-phase8" / "runtime" / "p8_runtime_support.c"
DRIVER_SOURCE = ROOT / ".openrecomp-phase8" / "runtime" / "p8_observable_driver.c"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class WorkflowResult(dict):
    """A deterministic workflow result record."""


def _fail(category: str, stage: str, detail: str) -> WorkflowResult:
    return WorkflowResult(
        workflow_version=WORKFLOW_VERSION,
        outcome=OUTCOME_FAIL_CLOSED,
        category=category,
        stage=stage,
        detail=detail[:400],
    )


def classify_and_analyze(data: bytes) -> tuple[Any, dict]:
    try:
        ingested = elf.ingest(data, target.MIPS32_O32)
    except (elf.ElfIngestError, ValueError) as exc:
        raise WorkflowFailure("UNSUPPORTED_ELF_CONTAINER", "classification", str(exc)) from exc
    region = ingested.parsed.executable_regions()[0]
    analysis = frontier.analyze(
        ingested.image.read_u32,
        region.p_vaddr,
        region.p_vaddr + region.p_memsz,
        ingested.parsed.header.e_entry,
    )
    return ingested, analysis


class WorkflowFailure(RuntimeError):
    def __init__(self, category: str, stage: str, detail: str = "") -> None:
        super().__init__(f"{category}@{stage}: {detail}")
        self.category = category
        self.stage = stage
        self.detail = detail


def _structure_and_coverage(ingested: Any, analysis: dict, data: bytes):
    source = ProgramSource(
        mips32_adapter.info.architecture_id,
        adapter="adapters.mips32",
        address_width_bits=32,
        endianness="little",
        input_sha256=sha256_bytes(data),
    )
    try:
        structure = structure_bridge.analyze_structure(
            analysis, source=source, entry=ingested.parsed.header.e_entry
        )
    except structure_bridge.P8StructureError as exc:
        if exc.code in ("UNSUPPORTED_CONTROL_TRANSFER", "RETURN_NOT_RA"):
            raise WorkflowFailure("UNSUPPORTED_ABI_REQUIREMENT", "structure", f"{exc.code}: {exc.detail}") from exc
        raise WorkflowFailure("UNSUPPORTED_ISA_SEMANTIC", "structure", f"{exc.code}: {exc.detail}") from exc

    summary = structure_bridge.structure_summary(structure)
    if summary["unresolved_sites"]:
        raise WorkflowFailure(
            "UNRESOLVED_INDIRECT_CONTROL_FLOW",
            "structure",
            json.dumps(summary["unresolved_sites"][:4]),
        )
    table = semantics.build_semantics()
    uncovered = []
    for instruction in structure.cfg.instructions:
        if not table.has(semantics.ARCHITECTURE, instruction.op):
            uncovered.append(f"0x{instruction.address:x}:{instruction.op}")
            continue
        if table.rule(semantics.ARCHITECTURE, instruction.op).flow is not instruction.flow:
            uncovered.append(f"0x{instruction.address:x}:{instruction.op}:flow")
    if uncovered:
        raise WorkflowFailure("UNSUPPORTED_ISA_SEMANTIC", "coverage", ",".join(uncovered[:8]))

    # ABI/memory-runtime requirements demonstrated by evidence.
    if ingested.identity["dynamic"] or ingested.identity["relocations"]:
        raise WorkflowFailure("UNSUPPORTED_ELF_CONTAINER", "classification", "dynamic/relocated ELF")
    return structure


def _memory_contract(ingested: Any):
    try:
        contract = contract_v1.build_contract(ingested)
    except (ValueError, KeyError) as exc:
        raise WorkflowFailure("UNSUPPORTED_MEMORY_RUNTIME", "memory-contract", str(exc)) from exc
    image = contract_v1.flat_image(ingested)
    if contract["stack"]["size"] == 0:
        raise WorkflowFailure("UNSUPPORTED_MEMORY_RUNTIME", "memory-contract", "empty stack")
    return contract, image


def _emit(structure: Any, contract: dict, image: bytes, fixture_sha256: str):
    try:
        build = emission.build_build_set(
            structure,
            contract,
            image,
            SUPPORT_SOURCE.read_text(encoding="utf-8"),
            DRIVER_SOURCE.read_text(encoding="utf-8"),
            fixture_sha256,
        )
    except HostEmitterError as exc:
        raise WorkflowFailure("UNSUPPORTED_ISA_SEMANTIC", "host-emission", str(exc)) from exc
    return build


def run_workflow(
    elf_path: pathlib.Path | str,
    *,
    workspace: pathlib.Path | None = None,
    do_build: bool = True,
    do_execute: bool = True,
    do_reference: bool = True,
    expected_observable: dict | None = None,
    compiler: str | None = None,
) -> WorkflowResult:
    """Run the deterministic bounded workflow on one ELF."""
    path = pathlib.Path(elf_path)
    stage = "input"
    try:
        data = path.read_bytes()
        stage = "classification"
        ingested, analysis = classify_and_analyze(data)
        stage = "analysis"
        if analysis["summary"]["reachable_invalid_words"]:
            raise WorkflowFailure(
                "UNSUPPORTED_ISA_SEMANTIC",
                "analysis",
                f"reachable invalid words: {analysis['summary']['reachable_invalid_words']}",
            )
        stage = "structure"
        structure = _structure_and_coverage(ingested, analysis, data)
        stage = "memory-contract"
        contract, image = _memory_contract(ingested)
        stage = "host-emission"
        build = _emit(structure, contract, image, sha256_bytes(data))

        record: WorkflowResult = WorkflowResult(
            workflow_version=WORKFLOW_VERSION,
            outcome=OUTCOME_COMPLETED,
            category=None,
            stage="completed",
            detail="",
            fixture_sha256=sha256_bytes(data),
            elf_identity=ingested.identity,
            frontier=analysis["summary"],
            structure=structure_bridge.structure_summary(structure),
            contract_digest=contract_v1.contract_digest(contract),
            emission=emission.emission_document(build),
        )

        if not do_build:
            return record

        stage = "native-build"
        try:
            toolchain = bp.discover_toolchain(compiler, raise_on_missing=False)
        except bp.BuildError as exc:
            raise WorkflowFailure("TOOLCHAIN_UNAVAILABLE", "native-build", str(exc)) from exc
        if toolchain is None:
            raise WorkflowFailure("TOOLCHAIN_UNAVAILABLE", "native-build", "clang-cl/lld-link not found")
        if workspace is None:
            raise WorkflowFailure("BUILD_FAILURE", "native-build", "workspace is required for builds")
        workspace = pathlib.Path(workspace)
        for run_dir in (workspace / "run1", workspace / "run2"):
            if run_dir.exists():
                shutil.rmtree(run_dir)
        comparison = bp.build_generated_host(
            lambda: build["files"]["program.c"],
            support_sources=(
                bp.BuildSource("p8_image_v1.c", bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE, build["files"]["p8_image_v1.c"].encode("utf-8")),
                bp.BuildSource("p8_runtime_support.c", bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE, build["files"]["p8_runtime_support.c"].encode("utf-8")),
                bp.BuildSource("p8_driver.c", bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE, build["files"]["p8_driver.c"].encode("utf-8")),
            ),
            config=bp.BuildConfig(fixture_id="p8-10-workflow", smoke_test=False, run_count=2),
            workspace=workspace,
            keep_workspace=True,
        )
        if any(run.manifest.build_status is not bp.BuildStatus.OK for run in comparison.runs):
            raise WorkflowFailure("BUILD_FAILURE", "native-build", "build status not OK")
        record["build"] = {
            "classification": comparison.classification.value,
            "executable_sha256": sha256_bytes((workspace / "run1" / "program.exe").read_bytes()),
        }
        if not do_execute:
            return record

        stage = "native-execution"
        completed = subprocess.run(
            [str(workspace / "run1" / "program.exe")],
            capture_output=True,
            timeout=600,
        )
        if completed.returncode != 0 or completed.stderr:
            raise WorkflowFailure("EXECUTION_FAILURE", "native-execution", completed.stderr[:200].decode("ascii", "replace"))
        native_stdout = completed.stdout.decode("utf-8")
        parsed: dict[str, Any] = {"registers": {}}
        for line in native_stdout.splitlines():
            if "=" not in line:
                continue
            key, value = line.strip().split("=", 1)
            if key.startswith("r") and len(key) == 3 and key[1:].isdigit():
                parsed["registers"][int(key[1:])] = value
            elif key == "registers":
                parsed["registers_digest"] = value
            elif key in ("transcript_len", "reads", "writes", "host_calls", "denied"):
                parsed[key] = int(value)
            else:
                parsed[key] = value
        record["native"] = {
            **{key: value for key, value in parsed.items() if key != "registers"},
            "registers": {f"r{index:02d}": parsed["registers"].get(index) for index in range(32)},
        }
        if parsed.get("failed") != "0":
            raise WorkflowFailure("EXECUTION_FAILURE", "native-execution", f"guest failure: {parsed.get('error')!r}")
        if parsed.get("exit_status") != "0x00000000":
            record["outcome"] = "COMPLETED_WITH_FRONTIER"
            record["detail"] = f"non-zero guest exit status {parsed.get('exit_status')}"

        if not do_reference:
            return record

        stage = "reference"
        try:
            loaded = reference.load_elf32(data)
            run = reference.execute(loaded)
        except reference.ReferenceError as exc:
            raise WorkflowFailure("REFERENCE_UNAVAILABLE", "reference", f"{exc.code}: {exc.detail}") from exc
        observed = run.to_observables()
        record["reference"] = observed

        stage = "equivalence"
        native_fields = {
            "exit_status": parsed.get("exit_status"),
            "registers_digest": parsed.get("registers_digest"),
            "memory_digest": parsed.get("memory"),
            "transcript_len": parsed.get("transcript_len"),
            "transcript_digest": parsed.get("transcript"),
            "reads": parsed.get("reads"),
            "writes": parsed.get("writes"),
            "host_calls": parsed.get("host_calls"),
            "denied": parsed.get("denied"),
        }
        reference_fields = {
            "exit_status": observed["exit_status"],
            "registers_digest": observed["registers_digest"],
            "memory_digest": observed["memory_digest"],
            "transcript_len": observed["transcript_len"],
            "transcript_digest": observed["transcript_digest"],
            "reads": observed["reads"],
            "writes": observed["writes"],
            "host_calls": observed["host_calls"],
            "denied": observed["denied"],
        }
        mismatches = {
            key: {"native": native_fields[key], "reference": reference_fields[key]}
            for key in native_fields
            if native_fields[key] != reference_fields[key]
        }
        for index in range(32):
            if parsed["registers"].get(index) != observed["registers"][f"r{index:02d}"]:
                mismatches[f"r{index:02d}"] = {
                    "native": parsed["registers"].get(index),
                    "reference": observed["registers"][f"r{index:02d}"],
                }
        if expected_observable is not None:
            for key, expected in expected_observable.items():
                actual = native_fields.get(key, parsed.get("registers", {}).get(key))
                if actual != expected:
                    mismatches[key] = {"native": actual, "expected": expected}
        if mismatches:
            raise WorkflowFailure("REFERENCE_MISMATCH", "equivalence", json.dumps(mismatches)[:400])
        record["equivalence"] = {"excluded_observables": [], "mismatches": {}}
        return record
    except WorkflowFailure as failure:
        return _fail(failure.category, failure.stage, failure.detail)
    except elf.ElfIngestError as exc:
        return _fail("UNSUPPORTED_ELF_CONTAINER", stage, str(exc))
    except OSError as exc:
        return _fail("INPUT_UNREADABLE", "input", str(exc))
    except Exception as exc:  # fail closed with a stable category
        return _fail("UNSUPPORTED_ISA_SEMANTIC", stage, f"{type(exc).__name__}: {exc}")
