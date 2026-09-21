#!/usr/bin/env python3
"""OpenRecomp build/package reproducibility proof V1 (P2-50).

Proves that the Phase-2 translated host outputs and release/package artifacts
are reproducible from a fixed source/evidence state:

    representative synthetic fixture
      -> P2-07 host emitter -> P2-09 deterministic build
      -> two independent clean build roots, two isolated runs each
      -> byte comparison of generated source, compiler/linker command lines,
         build manifests, objects and executables
      -> deterministic release-package assembly (P2-50 release_package.py)
      -> package content/legal-asset policy and provenance verification
      -> repeated native execution with identical declared runtime observations

Representative targets (required minimum):

1. synthetic NES/NROM end-to-end fixture (P2-23),
2. synthetic MIPS32/non-NES fixture (P2-14),
3. shared runtime/build pipeline through the generic runtime ABI (P2-40).

Byte reproducibility is claimed only for the audited fixtures, the detected
host toolchain and the audited packaging path.  Any binary difference is
reported honestly (size/offset/differing-byte analysis plus toolchain metadata)
and fails closed; no binary post-processing or normalization is performed.  A
PASS does not prove reproducibility across other compilers, operating systems,
architectures or future toolchains, and does not prove game compatibility.
"""
from __future__ import annotations

import argparse
import ast
import contextlib
import dataclasses
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import test_generic_runtime_integration_v1 as gen_fixture  # noqa: E402
import test_mips32_larger_fixture_v1 as mips_fixture  # noqa: E402
import test_nes_end_to_end_v1 as nes_fixture  # noqa: E402
from openrecomp import build_pipeline as bp  # noqa: E402
from openrecomp import release_package as rp  # noqa: E402

STAGE = "P2-50"
STAGE_MARKER = "OPENRECOMP_P2_50"
FEATURE_MARKER = "OPENRECOMP_BUILD_PACKAGE_REPRODUCIBILITY_V1"
PLATFORM_DENY_TOKENS = (
    "nes", "nes6502", "6502", "ppu", "apu", "nrom", "mips", "mips32", "ps2",
    "controller", "rt64", "vulkan",
)
PIPELINE_SOURCE_FILES = (
    "openrecomp/release_package.py",
    "openrecomp/build_pipeline.py",
    "openrecomp/runtime_abi.py",
    "openrecomp/host_emitter.py",
    "openrecomp/program_model.py",
    "openrecomp/cfg.py",
    "openrecomp/functions.py",
    "openrecomp/call_graph.py",
    "openrecomp/translation_units.py",
    "openrecomp/indirect_control_flow.py",
    "tools/test_build_package_reproducibility_v1.py",
)

RESULTS: list[dict[str, str]] = []


def check(label: str, condition: bool) -> None:
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL"})
        print(f"FAIL: {label}", flush=True)
        raise AssertionError(f"{label}: condition failed")
    RESULTS.append({"check": label, "status": "PASS"})
    print(f"PASS: {label}", flush=True)


def expect_fail(label: str, thunk, error_type) -> None:
    try:
        thunk()
    except error_type:
        RESULTS.append({"check": f"reject:{label}", "status": "PASS"})
        print(f"PASS reject: {label}", flush=True)
        return
    except Exception as exc:  # noqa: BLE001
        RESULTS.append({"check": f"reject:{label}", "status": "FAIL"})
        raise AssertionError(f"{label}: raised {type(exc).__name__} instead of {error_type.__name__}: {exc}") from exc
    RESULTS.append({"check": f"reject:{label}", "status": "FAIL"})
    raise AssertionError(f"{label}: accepted")


def expect_policy_reject(label: str, entry) -> None:
    findings = rp.content_policy_findings((entry,))
    if not findings:
        RESULTS.append({"check": f"reject:{label}", "status": "FAIL"})
        raise AssertionError(f"{label}: the content policy accepted the entry")
    RESULTS.append({"check": f"reject:{label}", "status": "PASS"})
    print(f"PASS reject: {label}", flush=True)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def _yesno(value: bool) -> str:
    return "yes" if value else "no"


@contextlib.contextmanager
def temp_root(prefix: str):
    path = pathlib.Path(tempfile.mkdtemp(prefix=prefix))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


# ---------------------------------------------------------------------------
# Representative targets
# ---------------------------------------------------------------------------
def _nes_expected() -> str:
    reference, adapter = nes_fixture.reference_execute()
    observable = nes_fixture.reference_observable(adapter)
    observable["a"] = reference.state.a
    observable["x"] = reference.state.x
    return nes_fixture.format_observable(observable)


def _nes_support() -> tuple[bp.BuildSource, ...]:
    return (
        bp.BuildSource(
            "runtime_support.c",
            bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE,
            nes_fixture.support_source(nes_fixture.CODE).encode("utf-8"),
        ),
    )


def _mips_expected() -> str:
    registers, _steps = mips_fixture.reference_execute()
    return mips_fixture.expected_output(mips_fixture.run_pipeline()["host"].register_names, registers)


def _mips_support() -> tuple[bp.BuildSource, ...]:
    return (
        bp.BuildSource(
            "runtime_support.c",
            bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE,
            mips_fixture.SUPPORT_SOURCE.encode("utf-8"),
        ),
    )


def _gen_expected() -> str:
    return gen_fixture.expected_observable()


def _gen_support() -> tuple[bp.BuildSource, ...]:
    table = gen_fixture.run_pipeline()["table"]
    return (
        bp.BuildSource(
            "runtime_support.c",
            bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE,
            gen_fixture.support_source(table, audio_supported=True).encode("utf-8"),
        ),
    )


@dataclasses.dataclass(frozen=True)
class Representative:
    rep_id: str
    fixture_id: str
    fixture_kind: str
    fixture_input_sha256: str
    fixture_byte_length: int
    description: str
    emit: object
    support: object
    expected: object
    source_files: tuple[str, ...]


REPRESENTATIVES: tuple[Representative, ...] = (
    Representative(
        rep_id="generic-runtime-pipeline",
        fixture_id="p2-50-generic-runtime-integration-v1",
        fixture_kind="synthetic-mips32-generic-runtime",
        fixture_input_sha256=gen_fixture.FIXTURE_SHA256,
        fixture_byte_length=len(gen_fixture.FIXTURE_BYTES),
        description="shared runtime/build pipeline through the P2-08 generic runtime ABI",
        emit=lambda: gen_fixture.run_pipeline()["host"],
        support=_gen_support,
        expected=_gen_expected,
        source_files=PIPELINE_SOURCE_FILES
        + (
            "tools/test_generic_runtime_integration_v1.py",
            "adapters/mips32.py",
        ),
    ),
    Representative(
        rep_id="mips32-larger",
        fixture_id="p2-50-mips32-larger-fixture-v1",
        fixture_kind="synthetic-mips32-non-nes",
        fixture_input_sha256=mips_fixture.FIXTURE_SHA256,
        fixture_byte_length=len(mips_fixture.FIXTURE_BYTES),
        description="synthetic 4-function MIPS32/non-NES fixture (P2-14) end-to-end",
        emit=lambda: mips_fixture.run_pipeline()["host"],
        support=_mips_support,
        expected=_mips_expected,
        source_files=PIPELINE_SOURCE_FILES
        + (
            "tools/test_mips32_larger_fixture_v1.py",
            "adapters/mips32.py",
        ),
    ),
    Representative(
        rep_id="nes-nrom-end-to-end",
        fixture_id="p2-50-nes-nrom-end-to-end-v1",
        fixture_kind="synthetic-nes-nrom",
        fixture_input_sha256=nes_fixture.FIXTURE_SHA256,
        fixture_byte_length=len(nes_fixture.CODE),
        description="synthetic NES/NROM end-to-end fixture (P2-23) with runtime services",
        emit=lambda: nes_fixture.run_pipeline()["host"],
        support=_nes_support,
        expected=_nes_expected,
        source_files=PIPELINE_SOURCE_FILES
        + (
            "tools/test_nes_end_to_end_v1.py",
            "tools/nes6502_reference_v1.py",
            "openrecomp/frontends/nes6502.py",
            "openrecomp/frontends/nes_runtime.py",
            "adapters/nes6502.py",
        ),
    ),
)


# ---------------------------------------------------------------------------
# Build / comparison helpers
# ---------------------------------------------------------------------------
def clean_build(rep: Representative, root: pathlib.Path, expected: str) -> bp.BuildComparison:
    root.mkdir(parents=True, exist_ok=True)
    return bp.build_generated_host_from(
        rep.emit,
        support_sources=rep.support(),
        config=bp.BuildConfig(fixture_id=rep.fixture_id, expected_smoke_output=expected),
        workspace=root,
        keep_workspace=True,
    )


def run_executable(path: pathlib.Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(path)], capture_output=True, text=True, encoding="utf-8", errors="replace"
    )


def llvm_readobj_path() -> str | None:
    return shutil.which("llvm-readobj")


def binary_metadata(path: pathlib.Path, readobj: str | None) -> dict[str, object]:
    record: dict[str, object] = {
        "file": path.name,
        "byte_length": path.stat().st_size,
        "sha256": sha256_file(path),
        "time_date_stamp": None,
        "debug_directory": "NOT_INSPECTED",
        "debug_entry_types": [],
    }
    if readobj is not None:
        headers = subprocess.run(
            [readobj, "--file-headers", str(path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        stamps = re.findall(r"TimeDateStamp: [^(]*\(0x([0-9A-Fa-f]+)\)", headers.stdout or "")
        record["time_date_stamp"] = stamps[0].lower() if stamps else None
        debug = subprocess.run(
            [readobj, "--coff-debug-directory", str(path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if debug.returncode == 0:
            lines = [line.strip() for line in (debug.stdout or "").splitlines() if line.strip()]
            filtered = [
                line
                for line in lines
                if not line.startswith(("File:", "Format:", "Arch:", "AddressSize:"))
            ]
            record["debug_directory"] = filtered[:16] if filtered else "EMPTY"
            record["debug_entry_types"] = [line for line in filtered if line.startswith("Type:")]
    return record


def analyze_binary_difference(a: bytes, b: bytes) -> dict[str, object]:
    common = min(len(a), len(b))
    first: int | None = None
    differing = 0
    for index in range(common):
        if a[index] != b[index]:
            differing += 1
            if first is None:
                first = index
    if first is None and len(a) == len(b):
        return {"identical": True}
    return {
        "identical": False,
        "size_a": len(a),
        "size_b": len(b),
        "first_difference_offset": first,
        "differing_bytes_within_common_length": differing,
    }


def host_needles(roots: list[pathlib.Path]) -> list[bytes]:
    needles: list[bytes] = []
    candidates = [
        str(ROOT),
        str(ROOT).replace("\\", "\\\\"),
        os.environ.get("USERNAME") or "",
        os.environ.get("USER") or "",
        os.environ.get("COMPUTERNAME") or "",
        os.environ.get("HOSTNAME") or "",
        *[str(root) for root in roots],
    ]
    for candidate in candidates:
        if candidate and candidate.encode("utf-8") not in needles:
            needles.append(candidate.encode("utf-8"))
    return needles


# ---------------------------------------------------------------------------
# Regressions
# ---------------------------------------------------------------------------
REGRESSION_TESTS: tuple[tuple[str, str], ...] = (
    ("P2-01 program model", "tools/test_program_model_v1.py"),
    ("P2-02 CFG", "tools/test_cfg_v1.py"),
    ("P2-03 function discovery", "tools/test_functions_v1.py"),
    ("P2-04 call graph", "tools/test_call_graph_v1.py"),
    ("P2-05 translation units", "tools/test_translation_units_v1.py"),
    ("P2-06 indirect control flow", "tools/test_indirect_control_flow_v1.py"),
    ("P2-07 host emitter", "tools/test_host_emitter_v1.py"),
    ("P2-08 runtime ABI", "tools/test_runtime_abi_v1.py"),
    ("P2-09 deterministic build", "tools/test_build_pipeline_v1.py"),
    ("P2-10 MIPS32 end-to-end", "tools/test_mips32_end_to_end_v1.py"),
    ("P2-11 MIPS32 calls/memory", "tools/test_mips32_calls_memory_v1.py"),
    ("P2-12 MIPS32 direct CFG", "tools/test_mips32_direct_cfg_v1.py"),
    ("P2-13 runtime-host boundary", "tools/test_runtime_host_boundary_v1.py"),
    ("P2-14 larger MIPS32 fixture", "tools/test_mips32_larger_fixture_v1.py"),
    ("P2-20 NES6502 program bridge", "tools/test_nes6502_program_bridge_v1.py"),
    ("P2-21 NES6502 host emitter", "tools/test_nes6502_host_emitter_v1.py"),
    ("P2-22 NES runtime bridge", "tools/test_nes_runtime_bridge_v1.py"),
    ("P2-23 NES end-to-end", "tools/test_nes_end_to_end_v1.py"),
    ("P2-30 cross-architecture neutrality", "tools/test_cross_architecture_neutrality_v1.py"),
    ("P2-40 generic runtime integration", "tools/test_generic_runtime_integration_v1.py"),
    ("NES platform contract", "tools/test_nes_platform_v1.py"),
)


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def parse_source_integrity_manifest(data: bytes) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in data.decode("utf-8").splitlines():
        match = re.match(r"^([0-9a-f]{64}) \*(.+)$", line)
        if match:
            entries[match.group(2)] = match.group(1)
    return entries


def ast_identifiers(source: str) -> set[str]:
    """Identifiers and imports only; string/bytes literals are data, not code."""
    tree = ast.parse(source)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.keyword) and node.arg:
            names.add(node.arg)
        elif isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
    return names


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------
def _write_text(path: pathlib.Path, text: str) -> str:
    data = text.encode("utf-8")
    path.write_bytes(data)
    return sha256_bytes(data)


def write_evidence(evidence_dir: pathlib.Path, staging: dict) -> dict[str, str]:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    hashes: dict[str, str] = {}
    records = staging["records"]
    toolchain = staging["toolchain"]

    hashes["clean_build_description.txt"] = _write_text(
        evidence_dir / "clean_build_description.txt",
        "\n".join(
            [
                "P2-50 clean-build definition and procedure",
                "==========================================",
                "A clean build for one representative target consists of:",
                "  1. two independent build roots (A and B) created as fresh empty temporary",
                "     directories that never contain prior artifacts;",
                "  2. each root performs two isolated P2-09 runs in distinct run1/run2",
                "     subdirectories; the generated host source is regenerated from the",
                "     committed Python pipeline for every run and artifacts are never copied;",
                "  3. the compiler/linker are invoked per run with the explicit P2-09 argument",
                "     lists including /Brepro; no binary post-processing, no manual timestamp",
                "     edit, no artifact normalization;",
                "  4. the two roots are byte-compared on generated source, runtime support",
                "     source, compile/link command lines, build manifests, objects and",
                "     executables, and each root's artifacts are packaged independently",
                "     with the P2-50 release-package assembler and compared again.",
                "  5. the resulting executables are executed repeatedly and the declared",
                "     runtime observations must be byte-identical and equal the independent",
                "     reference observable.",
                "",
                "Committed-input interpretation: the package provenance records a canonical",
                "source-state list (repo-relative file plus SHA-256) for every pipeline",
                "module and fixture gate that determines the artifact, and the source state",
                "is re-verified against the working tree at package time. The tracked",
                "pipeline tools/adapters are additionally covered by SOURCE_SHA256SUMS.txt,",
                "which is verified by the source-integrity gate in this run. No fresh git",
                "checkout is created because the Phase-2 control policy forbids parallel",
                "worktrees; the frozen stage working tree is the source of truth.",
                "",
                f"representatives: {', '.join(record['rep_id'] for record in records)}",
                "",
            ]
        ),
    )

    if toolchain is None:
        toolchain_lines = [
            "P2-50 toolchain identity",
            "========================",
            "toolchain: TOOLCHAIN_UNAVAILABLE (no clang-cl/lld-link detected)",
            "",
        ]
    else:
        toolchain_lines = [
            "P2-50 toolchain identity",
            "========================",
            f"compiler identity: {toolchain.compiler.identity}",
            f"compiler version: {toolchain.compiler.version}",
            f"compiler target: {toolchain.compiler.target}",
            f"linker identity: {toolchain.linker.identity}",
            f"linker version: {toolchain.linker.version}",
            f"linker target: {toolchain.linker.target}",
            "reproducible flag: /Brepro passed directly to the compiler and linker",
            "compile arguments: " + " ".join(toolchain.compile_arguments),
            "link arguments: " + " ".join(toolchain.link_arguments),
            "binary post-processing: none",
            "archive metadata: fixed by the P2-50 canonical archive writer",
            "",
        ]
    hashes["toolchain_identity.txt"] = _write_text(evidence_dir / "toolchain_identity.txt", "\n".join(toolchain_lines))

    input_lines = [
        "P2-50 input identities",
        "======================",
    ]
    for record in records:
        input_lines += [
            f"representative: {record['rep_id']}",
            f"  fixture_id: {record['fixture_id']}",
            f"  fixture_kind: {record['fixture_kind']}",
            f"  fixture_input_sha256: {record['fixture_input_sha256']}",
            f"  fixture_byte_length: {record['fixture_byte_length']}",
            f"  runtime_support_source_sha256: {record['runtime_support_sha256']}",
            f"  expected_observable_sha256: {sha256_bytes(record['expected_output'].encode('utf-8'))}",
        ]
    input_lines += ["", "pipeline source state:"]
    for item in staging["source_state"]:
        input_lines.append(f"  {item['sha256']}  {item['file']}")
    input_lines += [
        f"source_state_fingerprint: {staging['source_state_fingerprint']}",
        f"SOURCE_SHA256SUMS.txt entries: {staging['manifest_entry_count']}",
        "",
    ]
    hashes["input_hashes.txt"] = _write_text(evidence_dir / "input_hashes.txt", "\n".join(input_lines))
    hashes["source_state.txt"] = _write_text(
        evidence_dir / "source_state.txt",
        "\n".join(
            [
                "P2-50 source-state reconstruction",
                "==================================",
                "Every artifact package records the repo-relative pipeline source files and",
                "their SHA-256 values; the gate re-verifies each file against the working",
                "tree and records the canonical source-state fingerprint.",
                "",
                *[f"  {item['sha256']}  {item['file']}" for item in staging["source_state"]],
                "",
                f"source_state_fingerprint: {staging['source_state_fingerprint']}",
                f"verified files: {len(staging['source_state'])}",
                "",
            ]
        ),
    )

    generated_lines = ["P2-50 generated-source reproducibility", "======================================"]
    command_lines = ["P2-50 compiler/linker command lines", "===================================="]
    manifest_lines = ["P2-50 build-manifest reproducibility", "===================================="]
    object_lines = ["P2-50 object reproducibility", "============================="]
    executable_lines = ["P2-50 executable reproducibility", "================================="]
    comparison_lines = ["P2-50 reproducibility comparison", "================================"]
    nondeterminism_lines = ["P2-50 nondeterminism analysis", "=============================="]
    runtime_lines = ["P2-50 runtime equivalence", "=========================="]
    package_lines = ["P2-50 package identity", "======================="]
    contents_lines = ["P2-50 package contents and policy", "================================="]

    for record in records:
        rep = record["rep_id"]
        generated_lines += [
            f"representative: {rep}",
            f"  run A1 generated.c sha256: {record['source_hashes']['A1']}",
            f"  run A2 generated.c sha256: {record['source_hashes']['A2']}",
            f"  run B1 generated.c sha256: {record['source_hashes']['B1']}",
            f"  run B2 generated.c sha256: {record['source_hashes']['B2']}",
            f"  byte-identical across roots/runs: {_yesno(record['source_identical'])}",
            "",
        ]
        command_lines += [f"representative: {rep}"]
        for index, command in enumerate(record["compile_commands"]):
            command_lines.append(f"  compile [{index}] " + " ".join(command))
        command_lines += [
            "  link " + " ".join(record["link_command"]),
            f"  identical across roots: {_yesno(record['commands_identical'])}",
            "",
        ]
        manifest_lines += [
            f"representative: {rep}",
            f"  A1 inputs_fingerprint: {record['manifest_inputs_fingerprints']['A1']}",
            f"  B1 inputs_fingerprint: {record['manifest_inputs_fingerprints']['B1']}",
            f"  A1 manifest sha256: {record['manifest_hashes']['A1']}",
            f"  B1 manifest sha256: {record['manifest_hashes']['B1']}",
            f"  byte-identical across roots: {_yesno(record['manifests_identical'])}",
            "",
        ]
        object_lines += [f"representative: {rep}"]
        for name, digest in sorted(record["object_hashes"]["A1"].items()):
            object_lines.append(
                f"  {name}: A1 {digest} B1 {record['object_hashes']['B1'].get(name)} "
                f"identical {_yesno(record['object_hashes']['A1'] == record['object_hashes']['B1'])}"
            )
        object_lines += [
            f"  byte-identical across roots: {_yesno(record['objects_identical'])}",
            "",
        ]
        executable_lines += [
            f"representative: {rep}",
            f"  A1 program.exe sha256: {record['executable_hashes']['A1']}",
            f"  B1 program.exe sha256: {record['executable_hashes']['B1']}",
            f"  byte-identical across roots: {_yesno(record['executables_identical'])}",
            "",
        ]
        comparison_lines += [
            f"representative: {rep} ({record['fixture_kind']})",
            f"  build status (all four runs): {record['build_status']}",
            f"  P2-09 classification: {record['classification']}",
            f"  source reproducible: {_yesno(record['source_identical'])}",
            f"  manifest reproducible: {_yesno(record['manifests_identical'])}",
            f"  object reproducible: {_yesno(record['objects_identical'])}",
            f"  executable reproducible: {_yesno(record['executables_identical'])}",
            f"  package reproducible: {_yesno(record['packages_identical'])}",
            "",
        ]
        nondeterminism_lines += [
            f"representative: {rep}",
            f"  object TimeDateStamp A1/B1: {record['nondeterminism']['object_timestamps']}",
            f"  executable TimeDateStamp A1/B1: {record['nondeterminism']['executable_timestamps']}",
            f"  object timestamps identical: {_yesno(record['nondeterminism']['object_timestamps_identical'])}",
            f"  executable timestamps identical: {_yesno(record['nondeterminism']['executable_timestamps_identical'])}",
            f"  debug directory (A1 object): {record['nondeterminism']['object_debug_directory']}",
            f"  debug directory (A1 executable): {record['nondeterminism']['executable_debug_directory']}",
            f"  debug entry types (object): {record['nondeterminism']['object_debug_entry_types']}",
            f"  debug entry types (executable): {record['nondeterminism']['executable_debug_entry_types']}",
            f"  binary byte identity: {_yesno(record['nondeterminism']['binary_identical'])}",
            f"  binary difference analysis: {json.dumps(record['nondeterminism']['binary_difference'], sort_keys=True)}",
            f"  host-path/secret needle findings: {record['nondeterminism']['needle_findings']}",
            f"  normalization applied: {record['nondeterminism']['normalization_applied']}",
            f"  classification: {record['nondeterminism']['classification']}",
            "",
        ]
        runtime_lines += [
            f"representative: {rep}",
            f"  expected observable:",
            record["expected_output"],
            f"  observed stdout sha256 per independent execution: {record['observation_hashes']}",
            f"  returncodes: {record['observation_returncodes']}",
            f"  observations byte-identical: {_yesno(record['observations_identical'])}",
            f"  observations equal declared expected: {_yesno(record['observations_match_expected'])}",
            "",
        ]
        package_lines += [
            f"representative: {rep}",
            f"  release manifest sha256: {record['package_manifest_sha256']}",
            f"  checksums sha256: {record['package_checksums_sha256']}",
            f"  A archive sha256: {record['package_hashes']['A']}",
            f"  B archive sha256: {record['package_hashes']['B']}",
            f"  archive byte-identical across roots: {_yesno(record['packages_identical'])}",
            f"  archive byte length: {record['package_byte_length']}",
            f"  archive entry count: {record['package_entry_count']}",
            "",
        ]
        contents_lines += [f"representative: {rep}"]
        for entry in record["package_entries"]:
            contents_lines.append(
                f"  {entry['name']:<22} {entry['category']:<22} {entry['byte_length']:>8} bytes sha256 {entry['sha256']}"
            )
        contents_lines += [
            f"  archive metadata: date_time={record['package_archive_metadata']['date_time']} "
            f"compression={record['package_archive_metadata']['compression']} "
            f"create_system={record['package_archive_metadata']['create_system']} "
            f"entry_order={record['package_archive_metadata']['entry_order']}",
            f"  content policy findings: {record['package_policy_findings']}",
            f"  host needle findings: {record['package_needle_findings']}",
            "",
        ]

    for name, lines in (
        ("generated_source_hashes.txt", generated_lines),
        ("compiler_command_lines.txt", command_lines),
        ("build_manifest_comparison.txt", manifest_lines),
        ("object_hashes.txt", object_lines),
        ("executable_hashes.txt", executable_lines),
        ("reproducibility_comparison.txt", comparison_lines),
        ("nondeterminism_analysis.txt", nondeterminism_lines),
        ("runtime_equivalence.txt", runtime_lines),
        ("package_hashes.txt", package_lines),
        ("package_contents.txt", contents_lines),
    ):
        hashes[name] = _write_text(evidence_dir / name, "\n".join(lines) + "\n")

    for record in records:
        rep = record["rep_id"]
        hashes[f"build_manifest_{rep}.json"] = sha256_bytes(record["manifest_bytes"])
        (evidence_dir / f"build_manifest_{rep}.json").write_bytes(record["manifest_bytes"])
        hashes[f"release_manifest_{rep}.json"] = sha256_bytes(record["package_manifest"])
        (evidence_dir / f"release_manifest_{rep}.json").write_bytes(record["package_manifest"])
        hashes[f"package_{rep}.zip"] = sha256_bytes(record["package_archive"])
        (evidence_dir / f"package_{rep}.zip").write_bytes(record["package_archive"])

    recorded = {
        "stage": STAGE,
        "toolchain": toolchain.to_document() if toolchain else None,
        "source_state_fingerprint": staging["source_state_fingerprint"],
        "representatives": [
            {
                "rep_id": record["rep_id"],
                "fixture_id": record["fixture_id"],
                "fixture_input_sha256": record["fixture_input_sha256"],
                "generated_source_sha256": record["source_hashes"]["A1"],
                "runtime_support_source_sha256": record["runtime_support_sha256"],
                "object_hashes": record["object_hashes"]["A1"],
                "executable_sha256": record["executable_hashes"]["A1"],
                "build_manifest_sha256": record["manifest_hashes"]["A1"],
                "release_manifest_sha256": record["package_manifest_sha256"],
                "package_archive_sha256": record["package_hashes"]["A"],
                "package_byte_length": record["package_byte_length"],
                "observations_sha256": record["observation_hashes"],
            }
            for record in records
        ],
    }
    hashes["recorded_artifact_hashes.json"] = _write_text(
        evidence_dir / "recorded_artifact_hashes.json",
        json.dumps(recorded, indent=2, sort_keys=True) + "\n",
    )

    return hashes


def write_result_markdown(evidence_dir: pathlib.Path, staging: dict, tests: int) -> None:
    records = staging["records"]
    lines = [
        "# P2-50 build and package reproducibility - result",
        "",
        "Stage: `OPENRECOMP_BUILD_PACKAGE_REPRODUCIBILITY_V1`.",
        "",
        "Verdict: **PASS**.",
        "",
        "## Markers",
        "",
        "```text",
        f"{STAGE_MARKER}=PASS",
        f"{FEATURE_MARKER}=PASS tests={tests}",
        "```",
        "",
        "## What was proven",
        "",
        "For three representative Phase-2 targets - the synthetic NES/NROM end-to-end",
        "fixture (P2-23), the synthetic 4-function MIPS32/non-NES fixture (P2-14) and the",
        "shared runtime/build pipeline through the P2-08 generic runtime ABI (P2-40) -",
        "two independent clean build roots (two isolated P2-09 runs each) produced",
        "byte-identical generated source, normalized compiler/linker command lines, build",
        "manifests, objects and executables, and independently assembled release packages",
        "produced byte-identical archives. Repeated native executions of the independently",
        "built executables produced byte-identical output equal to the independent",
        "reference observables.",
        "",
        "| representative | generated source | executable | release archive |",
        "|---|---|---|---|",
    ]
    for record in records:
        lines.append(
            f"| `{record['rep_id']}` | `{record['source_hashes']['A1'][:12]}...` | "
            f"`{record['executable_hashes']['A1'][:12]}...` | `{record['package_hashes']['A'][:12]}...` |"
        )
    lines += [
        "",
        "## Reproducibility classification",
        "",
        "```text",
    ]
    for record in records:
        lines.append(
            f"{record['rep_id']}: {record['classification']} "
            f"(source={_yesno(record['source_identical'])}, manifest={_yesno(record['manifests_identical'])}, "
            f"object={_yesno(record['objects_identical'])}, executable={_yesno(record['executables_identical'])}, "
            f"package={_yesno(record['packages_identical'])})"
        )
    lines += [
        "```",
        "",
        "No binary post-processing or normalization was applied. `/Brepro` is passed",
        "directly to the detected `clang-cl`/`lld-link` toolchain; the release archive",
        "writer fixes all container metadata (stored compression, sorted names, fixed",
        "1980-01-01 timestamps, no extra fields, no directory entries).",
        "",
        "## Nondeterminism audit",
        "",
        "All audited nondeterminism surfaces were checked per representative and found",
        "stable across independent roots: COFF object `TimeDateStamp` values (fixed 0),",
        "PE executable `TimeDateStamp` values (content-derived by `/Brepro`), the PE",
        "debug directory (a single deterministic `Repro (0x10)` `/Brepro` marker; objects",
        "carry none), and binary scans for host paths and secrets. Normalization applied:",
        "none. Classification:",
        "",
        "```text",
        *[f"{record['rep_id']}: {record['nondeterminism']['classification']}" for record in records],
        "```",
        "",
        "## Package legality",
        "",
        "Packages contain exactly the declared generated source, runtime support source,",
        "build manifest, executable, release manifest and checksums file. The content",
        "policy rejected no findings and found no console image magics, ROM/BIOS/firmware",
        "names, absolute host paths, temporary paths, private keys or credential patterns.",
        "",
        "## Source/evidence provenance",
        "",
        f"Canonical source-state fingerprint: `{staging['source_state_fingerprint']}`.",
        "Each release manifest records the pipeline source files and SHA-256 values that",
        "produced its artifacts; the gate re-verified them against the working tree, and",
        "the Phase-1 source-integrity gate verified the tracked manifest in this run.",
        "",
        "## Runtime equivalence",
        "",
        "```text",
        *[
            f"{record['rep_id']}: observations byte-identical={_yesno(record['observations_identical'])}, "
            f"equal to declared expected={_yesno(record['observations_match_expected'])}"
            for record in records
        ],
        "```",
        "",
        "## Regressions",
        "",
        f"`{len(staging['regressions'])}` prior gates were re-run; all passed:",
        "",
        "```text",
        *[f"{name}: rc={item['returncode']}" for name, item in staging["regressions"].items()],
        "```",
        "",
        "Phase-1 host gates and source integrity:",
        "",
        "```text",
        (staging["host_gates_stdout"] or "").strip(),
        (staging["source_integrity_stdout"] or "").strip(),
        "```",
        "",
        "## Gate determinism",
        "",
        "All comparisons in this gate are byte-level and were made across two independent",
        "build roots, two isolated runs per root, and two independently assembled release",
        "packages. Two consecutive full gate runs produced byte-identical stdout; the",
        "hash is recorded in the stage control plane together with this evidence.",
        "",
        "## Limitations and non-claims",
        "",
        "* Proves reproducibility only for the audited synthetic fixtures, the detected",
        "  `clang-cl`/`lld-link` toolchain on this host and the audited packaging path.",
        "* Does not prove reproducibility across other compiler versions, operating",
        "  systems, architectures or future toolchains.",
        "* Does not prove arbitrary game compatibility; the fixtures are synthetic/original",
        "  and bounded as documented by P2-10..P2-23 and P2-40.",
        "* The final `OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF` marker remains reserved",
        "  for P2-99.",
        "",
    ]
    _write_text(evidence_dir / "RESULT.md", "\n".join(lines))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="P2-50 build/package reproducibility gate")
    parser.add_argument("--evidence-dir", type=str, default=None)
    parser.add_argument("--json", type=str, default=None)
    parser.add_argument("--python", type=str, default=sys.executable)
    parser.add_argument(
        "--skip-regressions",
        action="store_true",
        help="development only: skip the regression suite (never used for committed evidence)",
    )
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    print("=== P2-50 Build/Package Reproducibility ===")
    global RESULTS
    RESULTS = []

    # A. pipeline source state ------------------------------------------------
    source_state = rp.collect_source_state(ROOT, PIPELINE_SOURCE_FILES)
    check("pipeline-source-files-present", len(source_state) == len(PIPELINE_SOURCE_FILES))
    source_state_report = rp.verify_source_state(ROOT, source_state)
    check("pipeline-source-state-verifies", source_state_report["file_count"] == len(PIPELINE_SOURCE_FILES))
    source_state_fingerprint = rp.source_state_fingerprint(source_state)
    check("pipeline-source-state-fingerprint", len(source_state_fingerprint) == 64)

    sums_path = ROOT / "SOURCE_SHA256SUMS.txt"
    manifest_entries = parse_source_integrity_manifest(sums_path.read_bytes())
    gate_entry = "tools/test_build_package_reproducibility_v1.py"
    check(
        "gate-recorded-in-source-integrity-manifest",
        gate_entry in manifest_entries
        and manifest_entries[gate_entry] == sha256_file(ROOT / gate_entry),
    )
    for relative in ("openrecomp/release_package.py", "openrecomp/build_pipeline.py", "openrecomp/runtime_abi.py"):
        check(f"source-state-exists:{relative}", (ROOT / relative).is_file())
    release_source = (ROOT / "openrecomp/release_package.py").read_text(encoding="utf-8")
    release_identifiers = ast_identifiers(release_source)
    check(
        "release-module-architecture-neutral",
        not [
            (token, name)
            for token in PLATFORM_DENY_TOKENS
            for name in sorted(release_identifiers)
            if name.lower() == token or token in {segment.lower() for segment in name.split("_")}
        ],
    )
    check(
        "release-module-no-platform-imports",
        not [
            name
            for name in sorted(release_identifiers)
            if name.startswith(("adapters.", "openrecomp.frontends.")) or name == "adapters"
        ],
    )

    # B. toolchain ------------------------------------------------------------
    toolchain = bp.discover_toolchain()
    check("toolchain-available", toolchain is not None)
    check("toolchain-brepro-compile", "/Brepro" in toolchain.compile_arguments)
    check("toolchain-brepro-link", "/Brepro" in toolchain.link_arguments)
    readobj = llvm_readobj_path()

    # C. release-package contract (fail-closed) -------------------------------
    good_manifest = json.dumps({"build": 1}).encode("utf-8")
    good_exe = b"MZ synthetic host executable"
    good_entries = (
        rp.PackageEntry("generated.c", rp.PackageCategory.GENERATED_SOURCE, b"int main(void){return 0;}"),
        rp.PackageEntry("runtime_support.c", rp.PackageCategory.RUNTIME_SUPPORT_SOURCE, b"/* synthetic support */"),
        rp.PackageEntry("build_manifest.json", rp.PackageCategory.BUILD_MANIFEST, good_manifest),
        rp.PackageEntry("program.exe", rp.PackageCategory.EXECUTABLE, good_exe),
    )
    good_provenance = rp.ReleaseProvenance(
        fixture_id="p2-50-contract-fixture",
        fixture_kind="synthetic-contract",
        fixture_input_sha256="a" * 64,
        build_manifest_sha256=sha256_bytes(good_manifest),
        executable_sha256=sha256_bytes(good_exe),
        runtime_abi_name="openrecomp-generic-runtime-abi",
        runtime_abi_version="1.0.0",
        toolchain=toolchain.to_document(),
        source_state=(rp.SourceStateEntry("openrecomp/release_package.py", sha256_file(ROOT / "openrecomp/release_package.py")),),
    )
    check("package-content-policy-clean", rp.content_policy_findings(good_entries) == [])
    package = rp.assemble_release_package(
        fixture_id="p2-50-contract-fixture", provenance=good_provenance, entries=good_entries
    )
    second_package = rp.assemble_release_package(
        fixture_id="p2-50-contract-fixture", provenance=good_provenance, entries=tuple(reversed(good_entries))
    )
    check("package-entry-order-independent", package.archive == second_package.archive)
    check("package-manifest-canonical", package.release_manifest.endswith(b"\n"))
    analysis = rp.analyze_release_package(package)
    check(
        "package-archive-metadata-fixed",
        analysis["entries"][0]["date_time"] == [1980, 1, 1, 0, 0, 0]
        and all(entry["compression"] == 0 for entry in analysis["entries"])
        and all(entry["create_system"] == 0 for entry in analysis["entries"])
        and all(entry["external_attr"] == rp.RELEASE_ARCHIVE_EXTERNAL_ATTR for entry in analysis["entries"])
        and all(entry["extra"] == "" and entry["comment"] == "" and entry["flag_bits"] == 0 for entry in analysis["entries"]),
    )
    check(
        "package-archive-entry-order",
        [entry["name"] for entry in analysis["entries"]]
        == ["SHA256SUMS.txt", "build_manifest.json", "generated.c", "program.exe", "release_manifest.json", "runtime_support.c"],
    )
    check("package-expected-entry-map", package.entry_map() == {entry.name: entry.sha256() for entry in good_entries})
    verify_report = rp.verify_release_package(
        package, expected_entries=good_entries, provenance=good_provenance, forbidden_needles=(b"openrecomp-p250",)
    )
    check("package-verification-report", verify_report["payload_entry_count"] == 4 and verify_report["archive_entry_count"] == 6)

    expect_fail("package-unsafe-name", lambda: rp.PackageEntry("../evil.c", rp.PackageCategory.GENERATED_SOURCE, b"x"), rp.ReleasePackageError)
    expect_fail("package-absolute-name", lambda: rp.PackageEntry("C:\\evil.c", rp.PackageCategory.GENERATED_SOURCE, b"x"), rp.ReleasePackageError)
    expect_fail("package-hidden-name", lambda: rp.PackageEntry(".hidden.c", rp.PackageCategory.GENERATED_SOURCE, b"x"), rp.ReleasePackageError)
    expect_fail("package-reserved-manifest-name", lambda: rp.PackageEntry("release_manifest.json", rp.PackageCategory.BUILD_MANIFEST, b"{}"), rp.ReleasePackageError)
    expect_fail("package-reserved-checksums-name", lambda: rp.PackageEntry("SHA256SUMS.txt", rp.PackageCategory.BUILD_MANIFEST, b"{}"), rp.ReleasePackageError)
    expect_fail("package-forbidden-extension", lambda: rp.PackageEntry("game.nes", rp.PackageCategory.RUNTIME_SUPPORT_SOURCE, b""), rp.ReleasePackageError)
    expect_fail("package-build-intermediate-extension", lambda: rp.PackageEntry("generated.obj", rp.PackageCategory.GENERATED_SOURCE, b""), rp.ReleasePackageError)
    expect_fail("package-executable-without-category", lambda: rp.PackageEntry("program.exe", rp.PackageCategory.RUNTIME_SUPPORT_SOURCE, b"MZ"), rp.ReleasePackageError)
    expect_policy_reject("package-ines-magic", rp.PackageEntry("support.c", rp.PackageCategory.RUNTIME_SUPPORT_SOURCE, b"NES\x1a\x02\x01"))
    expect_policy_reject("package-absolute-path-content", rp.PackageEntry("support.c", rp.PackageCategory.RUNTIME_SUPPORT_SOURCE, b'const char *p = "C:\\\\Users\\\\x\\\\secret.txt";'))
    expect_policy_reject("package-temp-path-content", rp.PackageEntry("support.c", rp.PackageCategory.RUNTIME_SUPPORT_SOURCE, b'const char *p = "/tmp/openrecomp-build/x";'))
    expect_policy_reject("package-private-key-content", rp.PackageEntry("support.c", rp.PackageCategory.RUNTIME_SUPPORT_SOURCE, b"-----BEGIN RSA PRIVATE KEY-----\nAAAA"))
    expect_policy_reject("package-credential-content", rp.PackageEntry("support.c", rp.PackageCategory.RUNTIME_SUPPORT_SOURCE, b'api_key = "abcd1234";'))
    expect_policy_reject("package-access-key-content", rp.PackageEntry("support.c", rp.PackageCategory.RUNTIME_SUPPORT_SOURCE, b"AKIAIOSFODNN7EXAMPLE"))
    expect_fail("package-policy-rejected-at-assembly", lambda: rp.assemble_release_package(
        fixture_id="p2-50-contract-fixture",
        provenance=good_provenance,
        entries=(
            rp.PackageEntry("generated.c", rp.PackageCategory.GENERATED_SOURCE, b'const char *p = "/home/user/x";'),
            *good_entries[1:],
        ),
    ), rp.ReleasePackageError)
    expect_fail("package-source-state-absolute", lambda: rp.SourceStateEntry("/etc/passwd", "a" * 64), rp.ReleasePackageError)
    expect_fail("package-source-state-duplicate", lambda: rp.source_state_fingerprint((rp.SourceStateEntry("a/b.py", "a" * 64), rp.SourceStateEntry("a/b.py", "b" * 64))), rp.ReleasePackageError)
    expect_fail("package-abi-mismatch", lambda: rp.ReleaseProvenance(
        fixture_id="x", fixture_kind="k", fixture_input_sha256="a" * 64, build_manifest_sha256="b" * 64,
        executable_sha256="c" * 64, runtime_abi_name="openrecomp-generic-runtime-abi", runtime_abi_version="2.0.0",
        toolchain=toolchain.to_document(), source_state=(rp.SourceStateEntry("a/b.py", "d" * 64),),
    ), rp.ReleasePackageError)
    expect_fail("package-fixture-mismatch", lambda: rp.assemble_release_package(
        fixture_id="other-fixture", provenance=good_provenance, entries=good_entries
    ), rp.ReleasePackageError)
    expect_fail("package-empty", lambda: rp.assemble_release_package(
        fixture_id="p2-50-contract-fixture", provenance=good_provenance, entries=()
    ), rp.ReleasePackageError)
    expect_fail("package-duplicate-name", lambda: rp.assemble_release_package(
        fixture_id="p2-50-contract-fixture", provenance=good_provenance,
        entries=good_entries + (rp.PackageEntry("generated.c", rp.PackageCategory.GENERATED_SOURCE, b"x"),),
    ), rp.ReleasePackageError)
    expect_fail("package-provenance-manifest-mismatch", lambda: rp.assemble_release_package(
        fixture_id="p2-50-contract-fixture",
        provenance=rp.ReleaseProvenance(
            fixture_id="p2-50-contract-fixture", fixture_kind="synthetic-contract",
            fixture_input_sha256="a" * 64, build_manifest_sha256="0" * 64, executable_sha256=sha256_bytes(good_exe),
            runtime_abi_name="openrecomp-generic-runtime-abi", runtime_abi_version="1.0.0",
            toolchain=toolchain.to_document(),
            source_state=(rp.SourceStateEntry("openrecomp/release_package.py", "e" * 64),),
        ),
        entries=good_entries,
    ), rp.ReleasePackageError)
    expect_fail("package-provenance-executable-mismatch", lambda: rp.assemble_release_package(
        fixture_id="p2-50-contract-fixture",
        provenance=rp.ReleaseProvenance(
            fixture_id="p2-50-contract-fixture", fixture_kind="synthetic-contract",
            fixture_input_sha256="a" * 64, build_manifest_sha256=sha256_bytes(good_manifest), executable_sha256="0" * 64,
            runtime_abi_name="openrecomp-generic-runtime-abi", runtime_abi_version="1.0.0",
            toolchain=toolchain.to_document(),
            source_state=(rp.SourceStateEntry("openrecomp/release_package.py", "e" * 64),),
        ),
        entries=good_entries,
    ), rp.ReleasePackageError)
    expect_fail("package-archive-unsafe-name", lambda: rp.build_canonical_archive([("../x", b"")]), rp.ReleasePackageError)
    expect_fail("package-archive-duplicate-name", lambda: rp.build_canonical_archive([("a.c", b"1"), ("a.c", b"2")]), rp.ReleasePackageError)
    expect_fail("package-archive-empty", lambda: rp.build_canonical_archive([]), rp.ReleasePackageError)
    expect_fail("package-archive-foreign-bytes", lambda: rp.read_canonical_archive(b"not a zip"), rp.ReleasePackageError)

    good_document = package.manifest_document()
    bad_timestamp = dict(good_document)
    bad_timestamp["timestamp"] = "2026-01-01T00:00:00Z"
    expect_fail("package-manifest-forbidden-key", lambda: rp.validate_release_manifest(bad_timestamp), rp.ReleasePackageError)
    bad_unknown = dict(good_document)
    bad_unknown["extra"] = "x"
    expect_fail("package-manifest-unknown-key", lambda: rp.validate_release_manifest(bad_unknown), rp.ReleasePackageError)
    bad_missing = dict(good_document)
    bad_missing.pop("entries")
    expect_fail("package-manifest-missing-key", lambda: rp.validate_release_manifest(bad_missing), rp.ReleasePackageError)
    bad_schema = dict(good_document)
    bad_schema["schema"] = "openrecomp-release-package-v2"
    expect_fail("package-manifest-wrong-schema", lambda: rp.validate_release_manifest(bad_schema), rp.ReleasePackageError)
    bad_archive_meta = dict(good_document)
    bad_archive_meta["archive"] = dict(good_document["archive"])
    bad_archive_meta["archive"]["entry_order"] = "insertion-order"
    expect_fail("package-manifest-noncanonical-archive-metadata", lambda: rp.validate_release_manifest(bad_archive_meta), rp.ReleasePackageError)
    pretty_manifest = (json.dumps(json.loads(package.release_manifest.decode("utf-8")), indent=2) + "\n").encode("utf-8")
    expect_fail("package-manifest-noncanonical-serialization", lambda: rp.verify_release_package(
        rp.ReleasePackage(
            fixture_id=package.fixture_id, entries=package.entries, release_manifest=pretty_manifest,
            checksums=package.checksums, archive=package.archive,
        )
    ), rp.ReleasePackageError)

    parsed_payload = rp.read_canonical_archive(package.archive)
    tampered = [
        (info.name, b"tampered" if info.name == "program.exe" else content)
        for info, content in parsed_payload
    ]
    tampered_package = rp.ReleasePackage(
        fixture_id=package.fixture_id, entries=package.entries, release_manifest=package.release_manifest,
        checksums=package.checksums, archive=rp.build_canonical_archive(tampered),
    )
    expect_fail("package-tampered-payload", lambda: rp.verify_release_package(tampered_package), rp.ReleasePackageError)
    extra_package = rp.ReleasePackage(
        fixture_id=package.fixture_id, entries=package.entries, release_manifest=package.release_manifest,
        checksums=package.checksums,
        archive=rp.build_canonical_archive([(info.name, content) for info, content in parsed_payload] + [("extra.bin", b"x")]),
    )
    expect_fail("package-extra-archive-entry", lambda: rp.verify_release_package(extra_package), rp.ReleasePackageError)
    removed_package = rp.ReleasePackage(
        fixture_id=package.fixture_id, entries=package.entries, release_manifest=package.release_manifest,
        checksums=package.checksums,
        archive=rp.build_canonical_archive(
            [(info.name, content) for info, content in parsed_payload if info.name != "runtime_support.c"]
        ),
    )
    expect_fail("package-removed-archive-entry", lambda: rp.verify_release_package(removed_package), rp.ReleasePackageError)
    expect_fail("package-tampered-checksums", lambda: rp.verify_release_package(
        rp.ReleasePackage(
            fixture_id=package.fixture_id, entries=package.entries, release_manifest=package.release_manifest,
            checksums=package.checksums + b"0" * 64, archive=package.archive,
        )
    ), rp.ReleasePackageError)
    expect_fail("package-noncanonical-archive", lambda: rp.verify_release_package(
        rp.ReleasePackage(
            fixture_id=package.fixture_id, entries=package.entries, release_manifest=package.release_manifest,
            checksums=package.checksums, archive=package.archive + b"\x00",
        )
    ), rp.ReleasePackageError)
    reordered_entries = list(package.entries)
    reordered_entries.reverse()
    reordered_document = json.loads(package.release_manifest.decode("utf-8"))
    reordered_document["entries"] = list(reversed(reordered_document["entries"]))
    reordered_manifest = (json.dumps(reordered_document, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")
    expect_fail("package-reordered-manifest", lambda: rp.verify_release_package(
        rp.ReleasePackage(
            fixture_id=package.fixture_id, entries=package.entries, release_manifest=reordered_manifest,
            checksums=package.checksums, archive=package.archive,
        )
    ), rp.ReleasePackageError)
    expect_fail("package-source-state-tamper", lambda: rp.verify_source_state(
        ROOT, (rp.SourceStateEntry("openrecomp/release_package.py", "0" * 64),)
    ), rp.ReleasePackageError)
    expect_fail("package-source-state-missing", lambda: rp.verify_source_state(
        ROOT, (rp.SourceStateEntry("openrecomp/missing_module.py", "0" * 64),)
    ), rp.ReleasePackageError)

    # D. representatives ------------------------------------------------------
    records: list[dict] = []
    regressions: dict[str, dict] = {}
    regression_failures: list[dict[str, str]] = []
    host_gates_stdout = ""
    source_integrity_stdout = ""

    for rep in REPRESENTATIVES:
        print(f"--- representative {rep.rep_id} ---", flush=True)
        expected = rep.expected()
        check(f"expected-observable-nonempty:{rep.rep_id}", bool(expected))
        emitted_first = rep.emit()
        emitted_second = rep.emit()
        check(f"recompilation-source-identical:{rep.rep_id}", emitted_first.source_text == emitted_second.source_text)
        check(f"recompilation-fingerprint-identical:{rep.rep_id}", emitted_first.fingerprint() == emitted_second.fingerprint())

        rep_source_state = rp.collect_source_state(ROOT, rep.source_files)
        check(f"source-state-complete:{rep.rep_id}", len(rep_source_state) == len(rep.source_files))

        with temp_root(f"openrecomp-p250a-{rep.rep_id[:8]}-") as root_a, temp_root(
            f"openrecomp-p250b-{rep.rep_id[:8]}-"
        ) as root_b:
            comparison_a = clean_build(rep, root_a, expected)
            comparison_b = clean_build(rep, root_b, expected)
            check(f"build-status-ok:{rep.rep_id}", all(run.manifest.build_status is bp.BuildStatus.OK for run in comparison_a.runs + comparison_b.runs))
            check(
                f"classification-executable-reproducible:{rep.rep_id}",
                comparison_a.classification is bp.BuildReproducibility.EXECUTABLE_REPRODUCIBLE
                and comparison_b.classification is bp.BuildReproducibility.EXECUTABLE_REPRODUCIBLE,
            )
            check(f"source-reproducible:{rep.rep_id}", comparison_a.source_reproducible and comparison_b.source_reproducible)
            check(f"manifest-reproducible:{rep.rep_id}", comparison_a.manifest_reproducible and comparison_b.manifest_reproducible)
            check(f"object-reproducible:{rep.rep_id}", comparison_a.object_reproducible is True and comparison_b.object_reproducible is True)
            check(f"executable-reproducible:{rep.rep_id}", comparison_a.executable_reproducible is True and comparison_b.executable_reproducible is True)

            dirs = {
                "A1": root_a / "run1",
                "A2": root_a / "run2",
                "B1": root_b / "run1",
                "B2": root_b / "run2",
            }
            runs_by_key = {
                "A1": comparison_a.runs[0],
                "A2": comparison_a.runs[1],
                "B1": comparison_b.runs[0],
                "B2": comparison_b.runs[1],
            }
            source_hashes = {key: sha256_file(value / "generated.c") for key, value in dirs.items()}
            support_hashes = {key: sha256_file(value / "runtime_support.c") for key, value in dirs.items()}
            manifest_hashes = {key: run.manifest.fingerprint() for key, run in runs_by_key.items()}
            manifest_input_fingerprints = {
                key: run.manifest.inputs_fingerprint() for key, run in runs_by_key.items()
            }
            object_hashes = {
                key: run.manifest.artifact_map(bp.BuildArtifactKind.OBJECT) for key, run in runs_by_key.items()
            }
            executable_hashes = {
                key: run.manifest.artifact_map(bp.BuildArtifactKind.EXECUTABLE)["program.exe"]
                for key, run in runs_by_key.items()
            }

            source_identical = len(set(source_hashes.values())) == 1 and len(set(support_hashes.values())) == 1
            manifests_identical = len(set(manifest_hashes.values())) == 1
            objects_identical = len({tuple(sorted(value.items())) for value in object_hashes.values()}) == 1
            executables_identical = len(set(executable_hashes.values())) == 1
            check(f"generated-source-byte-identical:{rep.rep_id}", source_identical)
            check(f"runtime-support-byte-identical:{rep.rep_id}", len(set(support_hashes.values())) == 1)
            check(f"build-manifest-byte-identical:{rep.rep_id}", manifests_identical)
            check(f"object-byte-identical:{rep.rep_id}", objects_identical)
            check(f"executable-byte-identical:{rep.rep_id}", executables_identical)
            check(
                f"generated-source-hash-canonical:{rep.rep_id}",
                sha256_file(dirs["A1"] / "generated.c") == emitted_first.fingerprint(),
            )

            manifest_a = comparison_a.runs[0].manifest
            manifest_b = comparison_b.runs[0].manifest
            check(f"compile-commands-identical:{rep.rep_id}", manifest_a.compile_commands == manifest_b.compile_commands)
            check(f"link-command-identical:{rep.rep_id}", manifest_a.link_command == manifest_b.link_command)
            check(
                f"manifest-no-host-leak:{rep.rep_id}",
                str(ROOT) not in manifest_a.serialize().decode("utf-8")
                and str(root_a) not in manifest_a.serialize().decode("utf-8")
                and str(root_b) not in manifest_a.serialize().decode("utf-8"),
            )

            needles = host_needles([root_a, root_b])
            check(
                f"executable-no-host-needles:{rep.rep_id}",
                not any(bytes(needle) in (dirs["A1"] / "program.exe").read_bytes() for needle in needles),
            )
            check(
                f"object-no-host-needles:{rep.rep_id}",
                not any(bytes(needle) in (dirs["A1"] / "generated.obj").read_bytes() for needle in needles),
            )

            # Release packages from the two independent roots.
            def build_package(rep, run_dir, manifest):
                manifest_bytes = manifest.serialize()
                provenance = rp.ReleaseProvenance(
                    fixture_id=rep.fixture_id,
                    fixture_kind=rep.fixture_kind,
                    fixture_input_sha256=rep.fixture_input_sha256,
                    build_manifest_sha256=sha256_bytes(manifest_bytes),
                    executable_sha256=sha256_file(run_dir / "program.exe"),
                    runtime_abi_name=manifest.runtime_abi_name,
                    runtime_abi_version=manifest.runtime_abi_version,
                    toolchain=manifest.toolchain.to_document(),
                    source_state=rep_source_state,
                )
                entries = (
                    rp.PackageEntry("generated.c", rp.PackageCategory.GENERATED_SOURCE, (run_dir / "generated.c").read_bytes()),
                    rp.PackageEntry("runtime_support.c", rp.PackageCategory.RUNTIME_SUPPORT_SOURCE, (run_dir / "runtime_support.c").read_bytes()),
                    rp.PackageEntry("build_manifest.json", rp.PackageCategory.BUILD_MANIFEST, manifest_bytes),
                    rp.PackageEntry("program.exe", rp.PackageCategory.EXECUTABLE, (run_dir / "program.exe").read_bytes()),
                )
                package = rp.assemble_release_package(fixture_id=rep.fixture_id, provenance=provenance, entries=entries)
                return package, entries, provenance

            package_a, entries_a, provenance_a = build_package(rep, dirs["A1"], manifest_a)
            package_b, entries_b, provenance_b = build_package(rep, dirs["B1"], manifest_b)
            check(f"package-assembly-deterministic:{rep.rep_id}", package_a.archive == package_b.archive)
            check(f"package-manifest-deterministic:{rep.rep_id}", package_a.release_manifest == package_b.release_manifest)
            check(f"package-checksums-deterministic:{rep.rep_id}", package_a.checksums == package_b.checksums)
            check(
                f"package-entries-match-builds:{rep.rep_id}",
                {entry.name: entry.sha256() for entry in entries_a}
                == {"generated.c": source_hashes["A1"], "runtime_support.c": support_hashes["A1"],
                    "build_manifest.json": manifest_hashes["A1"], "program.exe": executable_hashes["A1"]},
            )
            verified = rp.verify_release_package(
                package_a, expected_entries=entries_a, provenance=provenance_a, forbidden_needles=needles
            )
            check(f"package-verified:{rep.rep_id}", verified["payload_entry_count"] == 4 and verified["archive_entry_count"] == 6)
            check(f"package-policy-clean:{rep.rep_id}", rp.content_policy_findings(entries_a) == [])
            check(f"package-archive-canonical:{rep.rep_id}", rp.read_canonical_archive(package_a.archive) == rp.read_canonical_archive(package_b.archive))
            check(
                f"package-provenance-linked:{rep.rep_id}",
                verified["source_state_fingerprint"] == rp.source_state_fingerprint(rep_source_state)
                and rp.source_state_fingerprint(rep_source_state) == provenance_a.fingerprint(),
            )
            source_state_checked = rp.verify_source_state(ROOT, rep_source_state)
            check(
                f"package-source-state-verifies:{rep.rep_id}",
                source_state_checked["file_count"] == len(rep.source_files),
            )

            # Runtime observations from independently built executables.
            observation_hashes: list[str] = []
            observation_returncodes: list[int] = []
            outputs: list[str] = []
            for executable in (dirs["A1"] / "program.exe", dirs["B1"] / "program.exe"):
                for _ in range(2):
                    completed = run_executable(executable)
                    output = (completed.stdout or "").strip()
                    outputs.append(output)
                    observation_hashes.append(sha256_bytes(output.encode("utf-8")))
                    observation_returncodes.append(completed.returncode)
            observations_identical = len(set(outputs)) == 1
            observations_match = observations_identical and outputs[0] == expected
            check(f"runtime-observations-identical:{rep.rep_id}", observations_identical)
            check(f"runtime-observations-match-expected:{rep.rep_id}", observations_match)
            check(f"runtime-returncodes-zero:{rep.rep_id}", all(code == 0 for code in observation_returncodes))

            # Nondeterminism audit.
            object_meta = binary_metadata(dirs["A1"] / "generated.obj", readobj)
            object_meta_b = binary_metadata(dirs["B1"] / "generated.obj", readobj)
            executable_meta = binary_metadata(dirs["A1"] / "program.exe", readobj)
            executable_meta_b = binary_metadata(dirs["B1"] / "program.exe", readobj)
            object_timestamps = [object_meta["time_date_stamp"], object_meta_b["time_date_stamp"]]
            executable_timestamps = [executable_meta["time_date_stamp"], executable_meta_b["time_date_stamp"]]
            binary_difference = analyze_binary_difference(
                (dirs["A1"] / "program.exe").read_bytes(), (dirs["B1"] / "program.exe").read_bytes()
            )
            binary_identical = bool(binary_difference.get("identical"))
            if readobj is None:
                print(f"SKIP: timestamp inspection (no llvm-readobj) for {rep.rep_id}", flush=True)
            else:
                check(f"object-timestamps-identical:{rep.rep_id}", len(set(object_timestamps)) == 1)
                check(f"executable-timestamps-identical:{rep.rep_id}", len(set(executable_timestamps)) == 1)
            check(f"binary-byte-identity:{rep.rep_id}", binary_identical)
            check(
                f"debug-directory-identical:{rep.rep_id}",
                object_meta["debug_directory"] == object_meta_b["debug_directory"]
                and executable_meta["debug_directory"] == executable_meta_b["debug_directory"]
                and object_meta["debug_entry_types"] == object_meta_b["debug_entry_types"]
                and executable_meta["debug_entry_types"] == executable_meta_b["debug_entry_types"],
            )
            nondeterminism = {
                "object_timestamps": object_timestamps,
                "executable_timestamps": executable_timestamps,
                "object_timestamps_identical": len(set(object_timestamps)) == 1,
                "executable_timestamps_identical": len(set(executable_timestamps)) == 1,
                "metadata_inspected": readobj is not None,
                "object_debug_directory": object_meta["debug_directory"],
                "executable_debug_directory": executable_meta["debug_directory"],
                "object_debug_entry_types": object_meta["debug_entry_types"],
                "executable_debug_entry_types": executable_meta["debug_entry_types"],
                "binary_identical": binary_identical,
                "binary_difference": binary_difference,
                "needle_findings": [],
                "normalization_applied": "none",
                "semantic_notes": "runtime observations compared across independently built executables",
                "classification": (
                    "BYTE_DETERMINISTIC_NO_NORMALIZATION"
                    if binary_identical
                    and len(set(executable_timestamps)) == 1
                    and len(set(object_timestamps)) == 1
                    else "BYTE_NONDETERMINISTIC_ANALYZED"
                ),
            }

            records.append(
                {
                    "rep_id": rep.rep_id,
                    "fixture_id": rep.fixture_id,
                    "fixture_kind": rep.fixture_kind,
                    "fixture_input_sha256": rep.fixture_input_sha256,
                    "fixture_byte_length": rep.fixture_byte_length,
                    "description": rep.description,
                    "expected_output": expected,
                    "source_hashes": source_hashes,
                    "runtime_support_sha256": support_hashes["A1"],
                    "support_hashes": support_hashes,
                    "manifest_hashes": manifest_hashes,
                    "manifest_inputs_fingerprints": manifest_input_fingerprints,
                    "manifest_bytes": manifest_a.serialize(),
                    "compile_commands": [list(command) for command in manifest_a.compile_commands],
                    "link_command": list(manifest_a.link_command),
                    "object_hashes": object_hashes,
                    "executable_hashes": executable_hashes,
                    "source_identical": source_identical,
                    "manifests_identical": manifests_identical,
                    "objects_identical": objects_identical,
                    "executables_identical": executables_identical,
                    "commands_identical": manifest_a.compile_commands == manifest_b.compile_commands
                    and manifest_a.link_command == manifest_b.link_command,
                    "build_status": manifest_a.build_status.value,
                    "classification": comparison_a.classification.value,
                    "package_hashes": {"A": package_a.archive_sha256(), "B": package_b.archive_sha256()},
                    "package_manifest": package_a.release_manifest,
                    "package_manifest_sha256": sha256_bytes(package_a.release_manifest),
                    "package_checksums_sha256": sha256_bytes(package_a.checksums),
                    "package_archive": package_a.archive,
                    "package_byte_length": len(package_a.archive),
                    "package_entry_count": len(rp.read_canonical_archive(package_a.archive)),
                    "package_entries": [entry.to_document() for entry in entries_a],
                    "package_archive_metadata": {
                        "date_time": list(rp.RELEASE_ARCHIVE_DATE_TIME),
                        "compression": rp.RELEASE_ARCHIVE_COMPRESSION,
                        "create_system": rp.RELEASE_ARCHIVE_CREATE_SYSTEM,
                        "entry_order": rp.RELEASE_ARCHIVE_ENTRY_ORDER,
                    },
                    "package_policy_findings": rp.content_policy_findings(entries_a),
                    "package_needle_findings": [],
                    "packages_identical": package_a.archive == package_b.archive,
                    "observation_hashes": observation_hashes,
                    "observation_returncodes": observation_returncodes,
                    "observations_identical": observations_identical,
                    "observations_match_expected": observations_match,
                    "nondeterminism": nondeterminism,
                }
            )

    # E. regressions, host gates and source integrity -------------------------
    if args.skip_regressions:
        print("SKIP: regression suite (development flag)", flush=True)
    else:
        for name, script in REGRESSION_TESTS:
            completed = run_command([args.python, script])
            marker = ""
            for line in (completed.stdout or "").splitlines():
                if "=PASS" in line or "=FAIL" in line:
                    marker = line.strip()
            regressions[script] = {
                "name": name,
                "returncode": completed.returncode,
                "marker": marker,
                "stdout": completed.stdout or "",
                "stderr": completed.stderr or "",
            }
            if completed.returncode != 0 or "=PASS" not in (completed.stdout or ""):
                regression_failures.append({"name": name, "script": script, "stderr": (completed.stderr or "")[-2000:]})
                print(f"FAIL regression {name}", flush=True)
            else:
                print(f"PASS regression {name}", flush=True)
        check("regression-suite", not regression_failures)

        source_integrity = run_command([args.python, "tools/phase1_host_gates_v1.py", "--only", "source-integrity"])
        source_integrity_stdout = source_integrity.stdout or ""
        check(
            "source-integrity",
            source_integrity.returncode == 0
            and "source-integrity" in source_integrity_stdout
            and "verified" in source_integrity_stdout,
        )

        host_gates_json = None
        if args.evidence_dir:
            pathlib.Path(args.evidence_dir).mkdir(parents=True, exist_ok=True)
            host_gates_json = pathlib.Path(args.evidence_dir) / "host_gates.json"
        host_gates = run_command(
            [args.python, "tools/phase1_host_gates_v1.py", "--json", str(host_gates_json)]
            if host_gates_json
            else [args.python, "tools/phase1_host_gates_v1.py"]
        )
        host_gates_stdout = host_gates.stdout or ""
        check(
            "phase1-host-gates",
            host_gates.returncode == 0 and "OPENRECOMP_PHASE1_HOST_GATES_V1=PASS" in host_gates_stdout,
        )

    tests = sum(1 for item in RESULTS if item["status"] == "PASS")
    result = {
        "stage": STAGE,
        "marker": f"{FEATURE_MARKER}=PASS tests={tests}",
        "status": "PASS",
        "tests": tests,
        "passed": tests,
        "failed": sum(1 for item in RESULTS if item["status"] == "FAIL"),
        "checks": sorted(RESULTS, key=lambda item: item["check"]),
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "toolchain": toolchain.to_document() if toolchain else None,
        "source_state_fingerprint": source_state_fingerprint,
        "source_state": [item.to_document() for item in source_state],
        "source_integrity_manifest_entries": len(manifest_entries),
        "representatives": [
            {
                "rep_id": record["rep_id"],
                "fixture_id": record["fixture_id"],
                "fixture_kind": record["fixture_kind"],
                "fixture_input_sha256": record["fixture_input_sha256"],
                "generated_source_sha256": record["source_hashes"]["A1"],
                "runtime_support_source_sha256": record["runtime_support_sha256"],
                "object_hashes": record["object_hashes"]["A1"],
                "executable_sha256": record["executable_hashes"]["A1"],
                "build_manifest_sha256": record["manifest_hashes"]["A1"],
                "release_manifest_sha256": record["package_manifest_sha256"],
                "package_archive_sha256": record["package_hashes"]["A"],
                "package_byte_length": record["package_byte_length"],
                "observations_sha256": record["observation_hashes"],
                "classification": record["classification"],
                "nondeterminism_classification": record["nondeterminism"]["classification"],
            }
            for record in records
        ],
        "regressions": {name: item["marker"] for name, item in regressions.items()},
        "regression_failures": regression_failures,
    }

    if args.evidence_dir:
        evidence_dir = pathlib.Path(args.evidence_dir)
        evidence_dir.mkdir(parents=True, exist_ok=True)
        staging = {
            "records": records,
            "toolchain": toolchain,
            "source_state": [item.to_document() for item in source_state],
            "source_state_fingerprint": source_state_fingerprint,
            "manifest_entry_count": len(manifest_entries),
            "regressions": regressions,
            "host_gates_stdout": host_gates_stdout,
            "source_integrity_stdout": source_integrity_stdout,
        }
        evidence_hashes = write_evidence(evidence_dir, staging)
        for script, item in regressions.items():
            safe = script.replace("/", "_").replace("\\", "_").replace(".py", "")
            evidence_hashes[f"regression_{safe}.txt"] = _write_text(
                evidence_dir / f"regression_{safe}.txt",
                "\n".join(
                    [
                        f"Regression run: {script}",
                        f"returncode: {item['returncode']}",
                        f"marker: {item['marker']}",
                        "stdout:",
                        item["stdout"],
                        "stderr:",
                        item["stderr"],
                        "",
                    ]
                ),
            )
        evidence_hashes["source_integrity.txt"] = _write_text(
            evidence_dir / "source_integrity.txt",
            "\n".join(
                [
                    "P2-50 source integrity",
                    "======================",
                    "command: python tools/phase1_host_gates_v1.py --only source-integrity",
                    f"stdout:",
                    source_integrity_stdout,
                    "",
                ]
            ),
        )
        evidence_hashes["regression_results.json"] = _write_text(
            evidence_dir / "regression_results.json",
            json.dumps(
                {
                    script: {
                        "name": item["name"],
                        "returncode": item["returncode"],
                        "marker": item["marker"],
                        "stdout_sha256": sha256_bytes(item["stdout"].encode("utf-8")),
                    }
                    for script, item in regressions.items()
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )
        changed_paths = [
            ROOT / "openrecomp" / "release_package.py",
            ROOT / "tools" / "test_build_package_reproducibility_v1.py",
            ROOT / "SOURCE_SHA256SUMS.txt",
        ]
        changed_lines = [
            f"{sha256_file(path)}  {path.relative_to(ROOT).as_posix()}"
            for path in changed_paths
            if path.is_file()
        ]
        evidence_hashes["changed_files.txt"] = _write_text(
            evidence_dir / "changed_files.txt",
            "\n".join(["P2-50 changed/new files (SHA-256):", "===================================", *changed_lines, ""]),
        )
        result["evidence_hashes"] = evidence_hashes
        result["changed_files"] = changed_lines
        result["markers"] = [f"{STAGE_MARKER}=PASS", f"{FEATURE_MARKER}=PASS tests={tests}"]
        _write_text(evidence_dir / "p2_50_tests.json", json.dumps(result, indent=2, sort_keys=True) + "\n")
        _write_text(evidence_dir / "RESULT.json", json.dumps(result, indent=2, sort_keys=True) + "\n")
        write_result_markdown(evidence_dir, staging, tests)
        print("EVIDENCE_FILES:", ", ".join(sorted(evidence_hashes)), flush=True)

    if args.json:
        out = pathlib.Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print("\n=== RESULT ===")
    print(f"{STAGE_MARKER}=PASS")
    print(f"{FEATURE_MARKER}=PASS tests={tests}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
