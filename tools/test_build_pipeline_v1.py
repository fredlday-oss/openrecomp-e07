#!/usr/bin/env python3
"""Fail-closed tests for the OpenRecomp deterministic build pipeline V1 (P2-09).

Proves `openrecomp/build_pipeline.py`: deterministic canonical build manifests,
independent isolated build runs, generated-source regeneration and byte identity,
explicit toolchain identity/version/target, explicit ordered compile/link
arguments, object and executable hash comparison, an honest reproducibility
classification, and fail-closed handling of source hash mismatches, ABI
mismatches, malformed manifests, duplicate outputs, unsupported compilers,
failed compilation and over-strong reproducibility claims.

The synthetic fixture is the P2-08 generic-runtime-ABI host-call fixture. When
`clang-cl` + `lld-link` are available the gate performs two genuinely
independent `/Brepro` builds in distinct directories and, when `llvm-readobj` is
available, inspects the PE/COFF headers directly. No compiler availability is
assumed and no artifact-equality claim is made beyond the hashes actually
observed. This is a build/execution smoke test, not guest/host equivalence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import openrecomp.build_pipeline as bp  # noqa: E402
from openrecomp import runtime_abi as rt  # noqa: E402
from openrecomp.host_emitter import HostEmitterConfig, emit_host_translation  # noqa: E402
from test_runtime_abi_v1 import (  # noqa: E402
    host_call_classification,
    host_call_program,
    host_call_rules,
    service_table,
)

FIXTURE_ID = "p2-08-runtime-host-call-v1"
EXPECTED_SMOKE = "42 0"

SUPPORT_SOURCE = """\
#include <stdio.h>
#include <stdint.h>
#include <stddef.h>

#define OR_RT_SERVICE_DEMO_MUL UINT64_C(1)

void openrecomp_run(void);
int openrecomp_failed(void);
const char *openrecomp_error(void);
size_t openrecomp_register_count(void);
uint64_t openrecomp_register_value(size_t index);

int or_rt_host_call(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value) {
    if (service_id != OR_RT_SERVICE_DEMO_MUL) return 6;
    if (argc != 2u || args == 0 || out_value == 0) return 8;
    *out_value = args[0] * args[1];
    return 0;
}

int or_rt_memory_read(uint64_t address, uint32_t width_bits, uint64_t *out_value) {
    (void)address; (void)width_bits; (void)out_value;
    return 13;
}

int or_rt_memory_write(uint64_t address, uint32_t width_bits, uint64_t value) {
    (void)address; (void)width_bits; (void)value;
    return 13;
}

const char *or_rt_failure_reason(int code) {
    (void)code;
    return "";
}

int main(void) {
    openrecomp_run();
    printf("%llu %d\\n", (unsigned long long)openrecomp_register_value(2), openrecomp_failed());
    return 0;
}
"""

RESULTS: list[dict[str, str]] = []


def check(label, condition):
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL"})
        raise AssertionError(f"{label}: condition failed")
    RESULTS.append({"check": label, "status": "PASS"})
    print(f"PASS: {label}")


def expect_fail(label, thunk, error_type=bp.BuildError):
    try:
        thunk()
    except error_type:
        RESULTS.append({"check": f"reject:{label}", "status": "PASS"})
        print(f"PASS reject: {label}")
        return
    except Exception as exc:  # noqa: BLE001
        RESULTS.append({"check": f"reject:{label}", "status": "FAIL"})
        raise AssertionError(f"{label}: raised {type(exc).__name__} instead of {error_type.__name__}: {exc}") from exc
    RESULTS.append({"check": f"reject:{label}", "status": "FAIL"})
    raise AssertionError(f"{label}: accepted")


def emit_fixture():
    abi = rt.RuntimeAbiConfig(services=service_table())
    units = host_call_program()
    classification = host_call_classification(units)
    return emit_host_translation(
        units,
        classification,
        config=HostEmitterConfig(
            semantics=host_call_rules(), entry_function="fn_1000", runtime_abi=abi
        ),
    )


def support_sources():
    return (
        bp.BuildSource(
            "runtime_support.c", bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE, SUPPORT_SOURCE.encode("utf-8")
        ),
    )


def config(**kwargs):
    kwargs.setdefault("expected_smoke_output", EXPECTED_SMOKE)
    return bp.BuildConfig(fixture_id=FIXTURE_ID, **kwargs)


def _yesno(value):
    return "yes" if value else "no"


def _is_utf8(data: bytes) -> bool:
    try:
        data.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def _write_text(path: Path, text: str) -> str:
    data = text.encode("utf-8")
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def _run_report(run, comparison) -> str:
    manifest = run.manifest
    lines = [
        f"P2-09 deterministic build run {run.index + 1}",
        "=" * 40,
        f"run_index: {run.index + 1}",
        f"build_status: {manifest.build_status.value}",
        f"fixture_id: {manifest.fixture_id}",
        f"runtime_abi: {manifest.runtime_abi_name} {manifest.runtime_abi_version}",
        "",
        "inputs (canonical order):",
    ]
    for index, item in enumerate(manifest.inputs):
        lines.append(f"  [{index}] {item.kind.value:<24} {item.name:<20} sha256 {item.sha256}")
    lines.append("")
    lines.append("compile commands (normalized, no absolute paths):")
    for index, command in enumerate(manifest.compile_commands):
        lines.append(f"  [{index}] " + " ".join(command))
    lines.append("")
    lines.append("link command (normalized, no absolute paths):")
    lines.append("  " + " ".join(manifest.link_command) if manifest.link_command else "  (not run)")
    lines.append("")
    lines.append("outputs (canonical order):")
    for index, artifact in enumerate(manifest.outputs):
        digest = artifact.sha256 if artifact.sha256 is not None else "NOT_AVAILABLE"
        lines.append(f"  [{index}] {artifact.kind.value:<12} {artifact.name:<22} sha256 {digest}")
    generated = next((item for item in manifest.inputs if item.kind is bp.BuildArtifactKind.GENERATED_SOURCE), None)
    lines.extend(
        [
            "",
            f"generated source sha256: {generated.sha256 if generated else 'NOT_AVAILABLE'}",
            f"smoke returncode: {run.smoke_returncode}",
            f"smoke stdout: {run.smoke_stdout}",
            f"manifest sha256: {manifest.fingerprint()}",
            f"classification: {comparison.classification.value}",
            "",
        ]
    )
    return "\n".join(lines)


def write_evidence(
    evidence_dir: Path,
    comparison,
    toolchain,
    object_timestamps,
    exe_timestamps,
    expected_smoke,
) -> dict:
    """Write deterministic UTF-8 evidence. The destination path is never embedded."""
    if evidence_dir.exists() and not evidence_dir.is_dir():
        raise bp.BuildError(f"evidence destination {evidence_dir.name!r} exists and is not a directory")
    evidence_dir.mkdir(parents=True, exist_ok=True)
    hashes: dict[str, str] = {}
    runs = comparison.runs
    run1 = runs[0].manifest
    run2 = runs[1].manifest if len(runs) > 1 else runs[0].manifest

    manifest_bytes = run1.serialize()
    (evidence_dir / "build_manifest.json").write_bytes(manifest_bytes)
    hashes["build_manifest.json"] = hashlib.sha256(manifest_bytes).hexdigest()

    for index, run in enumerate(runs[:2]):
        hashes[f"build_run_{index + 1}.txt"] = _write_text(
            evidence_dir / f"build_run_{index + 1}.txt", _run_report(run, comparison)
        )

    if toolchain is not None:
        compiler_lines = [
            "P2-09 toolchain identity",
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
            "",
        ]
    else:
        compiler_lines = [
            "P2-09 toolchain identity",
            "========================",
            "toolchain: TOOLCHAIN_UNAVAILABLE (no clang-cl/lld-link detected)",
            "",
        ]
    hashes["compiler_version.txt"] = _write_text(evidence_dir / "compiler_version.txt", "\n".join(compiler_lines))

    inputs1 = {item.name: item.sha256 for item in run1.inputs}
    inputs2 = {item.name: item.sha256 for item in run2.inputs}
    source_lines = ["P2-09 generated-source reproducibility", "======================================", ""]
    for name in sorted(inputs1):
        equal = inputs1.get(name) == inputs2.get(name)
        source_lines += [f"{name}:", f"  run 1: {inputs1.get(name)}", f"  run 2: {inputs2.get(name)}", f"  identical: {_yesno(equal)}", ""]
    source_lines += [f"source reproducible: {_yesno(comparison.source_reproducible)}", f"classification: {comparison.classification.value}", ""]
    hashes["source_hashes.txt"] = _write_text(evidence_dir / "source_hashes.txt", "\n".join(source_lines))

    objects1 = run1.artifact_map(bp.BuildArtifactKind.OBJECT)
    objects2 = run2.artifact_map(bp.BuildArtifactKind.OBJECT)
    object_lines = ["P2-09 object reproducibility", "=============================", ""]
    for name in sorted(objects1):
        equal = objects1.get(name) == objects2.get(name)
        object_lines += [f"{name}:", f"  run 1: {objects1.get(name)}", f"  run 2: {objects2.get(name)}", f"  identical: {_yesno(equal)}", ""]
    object_lines.append("COFF TimeDateStamp (llvm-readobj, inspected bytes):")
    if object_timestamps:
        for index, value in enumerate(object_timestamps):
            object_lines.append(f"  generated.obj run {index + 1}: {value}")
        object_lines.append(f"  identical: {_yesno(len(set(object_timestamps)) == 1)}")
    else:
        object_lines.append("  NOT_AVAILABLE (llvm-readobj not present)")
    object_lines += ["", f"object reproducible: {_yesno(comparison.object_reproducible)}", ""]
    hashes["object_hashes.txt"] = _write_text(evidence_dir / "object_hashes.txt", "\n".join(object_lines))

    exes1 = run1.artifact_map(bp.BuildArtifactKind.EXECUTABLE)
    exes2 = run2.artifact_map(bp.BuildArtifactKind.EXECUTABLE)
    exe_lines = ["P2-09 executable reproducibility", "=================================", ""]
    for name in sorted(exes1):
        equal = exes1.get(name) == exes2.get(name)
        exe_lines += [f"{name}:", f"  run 1: {exes1.get(name)}", f"  run 2: {exes2.get(name)}", f"  identical: {_yesno(equal)}", ""]
    exe_lines.append("PE TimeDateStamp (llvm-readobj, inspected bytes):")
    if exe_timestamps:
        for index, value in enumerate(exe_timestamps):
            exe_lines.append(f"  program.exe run {index + 1}: {value}")
        exe_lines.append(f"  identical: {_yesno(len(set(exe_timestamps)) == 1)}")
    else:
        exe_lines.append("  NOT_AVAILABLE (llvm-readobj not present)")
    exe_lines += ["", f"executable reproducible: {_yesno(comparison.executable_reproducible)}", ""]
    hashes["executable_hashes.txt"] = _write_text(evidence_dir / "executable_hashes.txt", "\n".join(exe_lines))

    smoke_lines = [
        "P2-09 execution smoke test",
        "==========================",
        "NOTE: bounded synthetic build/execution smoke test only; not guest/host equivalence.",
        "",
        f"expected observable: {expected_smoke}",
    ]
    smoke_pass = True
    for run in runs[:2]:
        ok = run.smoke_returncode == 0 and run.smoke_stdout == expected_smoke
        smoke_pass = smoke_pass and ok
        smoke_lines.append(
            f"run {run.index + 1} observed: {run.smoke_stdout} returncode={run.smoke_returncode} {'PASS' if ok else 'FAIL'}"
        )
    smoke_lines += ["", f"result: {'PASS' if smoke_pass else 'FAIL'}", ""]
    hashes["execution_smoke_test.txt"] = _write_text(evidence_dir / "execution_smoke_test.txt", "\n".join(smoke_lines))

    return hashes


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", help="write the deterministic test record here")
    parser.add_argument("--manifest-out", help="write the run-1 build manifest here")
    parser.add_argument("--evidence-dir", help="write deterministic UTF-8 build evidence here (output only)")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    toolchain = bp.discover_toolchain()
    compiler_available = toolchain is not None
    print(f"toolchain: {'available' if compiler_available else 'unavailable'}")

    # A. toolchain identity --------------------------------------------------
    if compiler_available:
        check("compiler-identity", toolchain.compiler.identity == "clang-cl.exe" or toolchain.compiler.identity.startswith("clang"))
        check("compiler-version-recorded", len(toolchain.compiler.version) > 0 and "clang" in toolchain.compiler.version.lower())
        check("compiler-target-recorded", toolchain.compiler.target == "x86_64-pc-windows-msvc")
        check("linker-identity", toolchain.linker.identity == "lld-link.exe")
        check("linker-version-recorded", "LLD" in toolchain.linker.version)
        check("compile-args-explicit", toolchain.compile_arguments == ("/c", "/Brepro", "/Od", "/std:c11", "/nologo"))
        check("link-args-explicit", toolchain.link_arguments == ("/Brepro", "/nologo"))
        check("compile-command-has-brepro", "/Brepro" in toolchain.compile_command("generated.c", "generated.obj"))
        check("link-command-has-brepro", "/Brepro" in toolchain.link_command(["generated.obj"], "program.exe"))
    else:
        print("SKIP: toolchain-identity (no clang-cl/lld-link on PATH)")

    # B. fail-closed toolchain discovery ------------------------------------
    expect_fail("unsupported-explicit-compiler", lambda: bp.discover_toolchain("definitely-not-a-real-compiler", raise_on_missing=True))
    check("explicit-compiler-discovery-none", bp.discover_toolchain("definitely-not-a-real-compiler") is None)

    # C. independent builds --------------------------------------------------
    workspace = Path(tempfile.mkdtemp(prefix="openrecomp-p209-gate-"))
    comparison = None
    object_timestamps: list[str] = []
    exe_timestamps: list[str] = []
    first_source = emit_fixture().source_text
    second_source = emit_fixture().source_text
    check("independent-source-regeneration", first_source == second_source and len(first_source) > 0)

    try:
        comparison = bp.build_generated_host_from(
            emit_fixture, support_sources=support_sources(), config=config(), workspace=workspace, keep_workspace=True
        )
        run1 = workspace / "run1"
        run2 = workspace / "run2"
        check("independent-build-directories", run1.is_dir() and run2.is_dir() and run1 != run2)
        check("both-runs-have-source", (run1 / "generated.c").is_file() and (run2 / "generated.c").is_file())
        check("runs-regenerated-source", (run1 / "generated.c").read_text(encoding="utf-8") == first_source)

        check("run-count", len(comparison.runs) == 2)
        check("build-status-ok", all(run.manifest.build_status is bp.BuildStatus.OK for run in comparison.runs))
        check("source-reproducible", comparison.source_reproducible)
        check("manifest-reproducible", comparison.manifest_reproducible)
        check("object-reproducible", comparison.object_reproducible is True)
        check("executable-reproducible", comparison.executable_reproducible is True)
        check("classification-executable", comparison.classification is bp.BuildReproducibility.EXECUTABLE_REPRODUCIBLE)

        manifest_a = comparison.runs[0].manifest
        manifest_b = comparison.runs[1].manifest
        check("manifest-byte-identity", manifest_a.serialize() == manifest_b.serialize())
        check("manifest-inputs-identity", manifest_a.inputs_fingerprint() == manifest_b.inputs_fingerprint())
        check("source-hash-identity", [i.sha256 for i in manifest_a.inputs] == [i.sha256 for i in manifest_b.inputs])
        check("object-hash-identity", manifest_a.artifact_map(bp.BuildArtifactKind.OBJECT) == manifest_b.artifact_map(bp.BuildArtifactKind.OBJECT))
        check("executable-hash-identity", manifest_a.artifact_map(bp.BuildArtifactKind.EXECUTABLE) == manifest_b.artifact_map(bp.BuildArtifactKind.EXECUTABLE))
        check("object-hashes-present", all(manifest_a.artifact_map(bp.BuildArtifactKind.OBJECT).values()))

        # D. canonical manifest ---------------------------------------------
        document = manifest_a.to_document()
        serialized = manifest_a.serialize().decode("utf-8")
        check("canonical-json", serialized.rstrip("\n") == bp._canonical_json(json.loads(serialized)))
        check("sorted-top-level-keys", list(json.loads(serialized).keys()) == sorted(json.loads(serialized).keys()))
        check("schema-recorded", document["schema"] == bp.BUILD_MANIFEST_SCHEMA)
        check("manifest-version-recorded", document["manifest_version"] == bp.BUILD_MANIFEST_VERSION)
        check("stage-recorded", document["stage"] == "P2-09")
        check("fixture-id-recorded", document["fixture_id"] == FIXTURE_ID)
        check("runtime-abi-recorded", document["runtime_abi"] == {"name": rt.RUNTIME_ABI_NAME, "version": "1.0.0"})
        check("compiler-recorded", document["toolchain"]["compiler"]["identity"].startswith("clang"))
        check("linker-recorded", document["toolchain"]["linker"]["identity"] == "lld-link.exe")
        check("inputs-canonical-order", [i["name"] for i in document["inputs"]] == sorted(i["name"] for i in document["inputs"]))
        check("outputs-objects-first", [o["kind"] for o in document["outputs"]] == ["OBJECT", "OBJECT", "EXECUTABLE"])
        check("compile-commands-recorded", len(document["compile_commands"]) == len(document["inputs"]))
        check("link-command-recorded", document["link_command"][0].startswith("lld-link"))
        check("build-status-recorded", document["build_status"] == "OK")
        check("reproducibility-recorded", document["reproducibility"] == "EXECUTABLE_REPRODUCIBLE")
        check("deterministic-config-recorded", document["deterministic_config"]["runtime_abi_version"] == "1.0.0")

        # E. no nondeterministic / machine-specific fields -------------------
        forbidden = ("timestamp", "pid", "uuid", "hostname", "username", "cwd", "temp", "tmp", "mtime", "date")
        check("manifest-no-forbidden-keys", not any(key in serialized.lower() for key in forbidden))
        check("manifest-no-absolute-repo-path", str(ROOT).replace("\\", "\\\\") not in serialized and str(ROOT) not in serialized)
        check("manifest-no-build-root", str(workspace) not in serialized and workspace.name not in serialized)
        check("manifest-no-username", os.environ.get("USERNAME", "\x00") not in serialized and os.environ.get("USER", "\x00") not in serialized)
        check("manifest-no-hostname", os.environ.get("COMPUTERNAME", "\x00") not in serialized)
        check("manifest-no-drive-letter", not re.search(r"[A-Za-z]:\\\\", serialized))
        check("manifest-no-python-identity", "object at 0x" not in serialized and "<class" not in serialized)

        # F. manifest round-trip and artifact verification -------------------
        rebuilt = bp.BuildManifest.from_document(document, toolchain=toolchain)
        check("manifest-roundtrip-identity", rebuilt.fingerprint() == manifest_a.fingerprint())
        observed = {
            name: hashlib.sha256((run1 / name).read_bytes()).hexdigest()
            for name in manifest_a.artifact_map()
        }
        bp.verify_artifact_hashes(manifest_a, observed)
        check("artifact-verification-passes", True)
        tampered = dict(observed)
        tampered["program.exe"] = "0" * 64
        expect_fail("artifact-hash-mismatch", lambda: bp.verify_artifact_hashes(manifest_a, tampered))

        # G. smoke test ------------------------------------------------------
        smoke = [run.smoke_stdout for run in comparison.runs]
        check("smoke-output", smoke == [EXPECTED_SMOKE, EXPECTED_SMOKE])
        check("smoke-returncode", all(run.smoke_returncode == 0 for run in comparison.runs))

        # H. cross-directory root --------------------------------------------
        other_root = Path(tempfile.mkdtemp(prefix="openrecomp-p209-alt-"))
        try:
            cross = bp.build_generated_host_from(
                emit_fixture, support_sources=support_sources(), config=config(), workspace=other_root
            )
            check("cross-root-source-identity", cross.source_reproducible)
            check("cross-root-object-identity", cross.object_reproducible is True)
            check("cross-root-executable-identity", cross.executable_reproducible is True)
            check(
                "cross-root-exe-hash-match",
                cross.runs[0].manifest.artifact_map(bp.BuildArtifactKind.EXECUTABLE)
                == manifest_a.artifact_map(bp.BuildArtifactKind.EXECUTABLE),
            )
        finally:
            shutil.rmtree(other_root, ignore_errors=True)

        # I. PE/COFF header inspection --------------------------------------
        readobj = shutil.which("llvm-readobj")
        if readobj is None:
            print("SKIP: pe-coff-header-inspection (no llvm-readobj on PATH)")
        else:
            headers = subprocess.run(
                [readobj, "--file-headers", str(run1 / "generated.obj"), str(run2 / "generated.obj")],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
            )
            obj_timestamps = re.findall(r"TimeDateStamp: [^(]*\(0x([0-9A-Fa-f]+)\)", headers.stdout)
            object_timestamps = list(obj_timestamps)
            check("object-timestamp-zero", obj_timestamps == ["0", "0"])
            exe_headers = subprocess.run(
                [readobj, "--file-headers", str(run1 / "program.exe"), str(run2 / "program.exe")],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
            )
            exe_stamps = re.findall(r"TimeDateStamp: [^(]*\(0x([0-9A-Fa-f]+)\)", exe_headers.stdout)
            exe_timestamps = list(exe_stamps)
            check("executable-timestamp-identical", len(exe_stamps) == 2 and exe_stamps[0] == exe_stamps[1])

        # J. binary leakage check -------------------------------------------
        strings_tool = shutil.which("llvm-strings")
        if strings_tool is None:
            print("SKIP: binary-leakage-check (no llvm-strings on PATH)")
        else:
            needles = [str(workspace), workspace.name, str(ROOT), os.environ.get("USERNAME", "\x00"), os.environ.get("COMPUTERNAME", "\x00")]
            for name in ("generated.obj", "runtime_support.obj", "program.exe"):
                data = (run1 / name).read_bytes()
                check(f"no-path-leak:{name}", not any(needle.encode("utf-8", "ignore") in data for needle in needles if needle))

        # O. evidence-path independence (output-only mode) -------------------
        ev_a = Path(tempfile.mkdtemp(prefix="openrecomp-p209-evA-"))
        ev_b = Path(tempfile.mkdtemp(prefix="openrecomp-p209-evB-"))
        try:
            write_evidence(ev_a, comparison, toolchain, object_timestamps, exe_timestamps, EXPECTED_SMOKE)
            write_evidence(ev_b, comparison, toolchain, object_timestamps, exe_timestamps, EXPECTED_SMOKE)
            files_a = sorted(p.name for p in ev_a.iterdir() if p.is_file())
            files_b = sorted(p.name for p in ev_b.iterdir() if p.is_file())
            required = {
                "build_manifest.json", "build_run_1.txt", "build_run_2.txt", "compiler_version.txt",
                "source_hashes.txt", "object_hashes.txt", "executable_hashes.txt", "execution_smoke_test.txt",
            }
            check("evidence-file-set-complete", set(files_a) == required)
            check("evidence-file-set-identical", files_a == files_b)
            check(
                "evidence-cross-directory-identity",
                all((ev_a / name).read_bytes() == (ev_b / name).read_bytes() for name in files_a),
            )
            check("evidence-manifest-identical", (ev_a / "build_manifest.json").read_bytes() == (ev_b / "build_manifest.json").read_bytes())
            check("evidence-manifest-matches-gate", (ev_a / "build_manifest.json").read_bytes() == manifest_a.serialize())
            check("evidence-run-reports-distinct", (ev_a / "build_run_1.txt").read_bytes() != (ev_a / "build_run_2.txt").read_bytes())
            check(
                "evidence-text-utf8-clean",
                all(
                    not (ev_a / name).read_bytes().startswith((b"\xff\xfe", b"\xfe\xff", b"\xef\xbb\xbf"))
                    and b"\x00" not in (ev_a / name).read_bytes()
                    and _is_utf8((ev_a / name).read_bytes())
                    for name in files_a
                ),
            )
            evidence_text_bytes = b"".join((ev_a / name).read_bytes() for name in files_a)
            check(
                "evidence-no-output-root-leak",
                str(ev_a).encode("utf-8") not in evidence_text_bytes
                and str(ev_b).encode("utf-8") not in evidence_text_bytes,
            )
            check("evidence-no-repo-path-leak", str(ROOT).encode("utf-8") not in evidence_text_bytes)
            check("evidence-no-temp-root-leak", str(workspace).encode("utf-8") not in evidence_text_bytes)
            username = os.environ.get("USERNAME") or os.environ.get("USER")
            hostname = os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME")
            check("evidence-no-username-leak", not username or username.encode("utf-8") not in evidence_text_bytes)
            check("evidence-no-hostname-leak", not hostname or hostname.encode("utf-8") not in evidence_text_bytes)

            a_manifest = bp.BuildManifest.deserialize((ev_a / "build_manifest.json").read_bytes(), toolchain=toolchain)
            b_manifest = bp.BuildManifest.deserialize((ev_b / "build_manifest.json").read_bytes(), toolchain=toolchain)
            check("evidence-manifest-semantics-unchanged", a_manifest.fingerprint() == manifest_a.fingerprint() == b_manifest.fingerprint())
            check(
                "evidence-artifact-hashes-unchanged",
                a_manifest.artifact_map(bp.BuildArtifactKind.OBJECT) == manifest_a.artifact_map(bp.BuildArtifactKind.OBJECT)
                and a_manifest.artifact_map(bp.BuildArtifactKind.EXECUTABLE) == manifest_a.artifact_map(bp.BuildArtifactKind.EXECUTABLE),
            )
            check(
                "evidence-input-hashes-unchanged",
                [item.sha256 for item in a_manifest.inputs] == [item.sha256 for item in manifest_a.inputs],
            )
            check("evidence-classification-unchanged", a_manifest.reproducibility is comparison.classification)
            check("evidence-abi-version-unchanged", a_manifest.runtime_abi_version == rt.RUNTIME_ABI_VERSION)
            check("evidence-compiler-unchanged", a_manifest.toolchain.compiler == manifest_a.toolchain.compiler)
            check("evidence-linker-unchanged", a_manifest.toolchain.linker == manifest_a.toolchain.linker)
            check("evidence-compile-args-unchanged", a_manifest.compile_commands == manifest_a.compile_commands)
            check("evidence-link-args-unchanged", a_manifest.link_command == manifest_a.link_command)

            # Failure paths for the evidence destination.
            collision = Path(tempfile.mkdtemp(prefix="openrecomp-p209-evC-")) / "occupied"
            collision.write_text("not a directory", encoding="utf-8")
            try:
                expect_fail(
                    "evidence-destination-is-file",
                    lambda: write_evidence(collision, comparison, toolchain, object_timestamps, exe_timestamps, EXPECTED_SMOKE),
                )
            finally:
                shutil.rmtree(collision.parent, ignore_errors=True)
        finally:
            shutil.rmtree(ev_a, ignore_errors=True)
            shutil.rmtree(ev_b, ignore_errors=True)
    finally:
        if comparison is None or comparison.runs[0].manifest.build_status is not bp.BuildStatus.OK:
            pass
        shutil.rmtree(workspace, ignore_errors=True)

    # K. fail-closed contract ------------------------------------------------
    expect_fail("config-abi-mismatch", lambda: bp.BuildConfig(fixture_id=FIXTURE_ID, runtime_abi_version="2.0.0", expected_smoke_output=EXPECTED_SMOKE))
    expect_fail("config-reproducible-single-run", lambda: bp.BuildConfig(fixture_id=FIXTURE_ID, reproducible=True, run_count=1, expected_smoke_output=EXPECTED_SMOKE))
    expect_fail("config-smoke-without-expected", lambda: bp.BuildConfig(fixture_id=FIXTURE_ID, smoke_test=True))
    expect_fail("config-empty-fixture", lambda: bp.BuildConfig(fixture_id="", expected_smoke_output=EXPECTED_SMOKE))
    expect_fail("config-bad-source-hash", lambda: bp.BuildConfig(fixture_id=FIXTURE_ID, expected_smoke_output=EXPECTED_SMOKE, expected_source_hashes=(("generated.c", "nothex"),)))

    good_hashes = tuple(sorted((item.name, item.sha256()) for item in (bp.BuildSource("generated.c", bp.BuildArtifactKind.GENERATED_SOURCE, emit_fixture().source_text.encode()), bp.BuildSource("runtime_support.c", bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE, SUPPORT_SOURCE.encode()))))
    wrong_hashes = tuple((name, "0" * 64 if name == "generated.c" else digest) for name, digest in good_hashes)
    expect_fail(
        "source-hash-mismatch",
        lambda: bp.build_generated_host_from(
            emit_fixture,
            support_sources=support_sources(),
            config=config(smoke_test=False, expected_smoke_output=None, expected_source_hashes=wrong_hashes),
        ),
    )

    baseline_manifest = comparison.runs[0].manifest if comparison is not None else None
    if baseline_manifest is None:
        # Build a source-only manifest without the toolchain to exercise validation.
        baseline_manifest = bp.build_generated_host(
            emit_fixture, support_sources=support_sources(), config=config(smoke_test=False, expected_smoke_output=None)
        ).runs[0].manifest
    baseline_document = baseline_manifest.to_document()

    bad_document = dict(baseline_document)
    bad_document["timestamp"] = "2026-01-01T00:00:00Z"
    expect_fail("manifest-forbidden-timestamp", lambda: bp.BuildManifest.from_document(bad_document))

    missing = dict(baseline_document)
    missing.pop("build_status")
    expect_fail("manifest-missing-key", lambda: bp.BuildManifest.from_document(missing))

    bad_abi = dict(baseline_document)
    bad_abi["runtime_abi"] = {"name": rt.RUNTIME_ABI_NAME, "version": "2.0.0"}
    expect_fail("manifest-abi-mismatch", lambda: bp.BuildManifest.from_document(bad_abi))

    unknown_key = dict(baseline_document)
    unknown_key["extra"] = "x"
    expect_fail("manifest-unknown-key", lambda: bp.BuildManifest.from_document(unknown_key))

    expect_fail("manifest-not-json", lambda: bp.BuildManifest.deserialize(b"{not json"))

    duplicate_sources = (
        bp.BuildSource("x.c", bp.BuildArtifactKind.GENERATED_SOURCE, b"int a;\n"),
        bp.BuildSource("x.h", bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE, b"int b;\n"),
    )
    expect_fail(
        "duplicate-output",
        lambda: bp.build_generated_host(lambda: "int z;\n", support_sources=duplicate_sources, config=config(smoke_test=False, expected_smoke_output=None)),
    )
    expect_fail("bad-source-name", lambda: bp.BuildSource("../evil.c", bp.BuildArtifactKind.GENERATED_SOURCE, b"x"))
    expect_fail("absolute-source-name", lambda: bp.BuildSource("C:\\evil.c", bp.BuildArtifactKind.GENERATED_SOURCE, b"x"))

    failed = bp.build_generated_host(lambda: "this is not valid C\n", support_sources=(), config=bp.BuildConfig(fixture_id=FIXTURE_ID, smoke_test=False))
    check("failed-compile-status", all(run.manifest.build_status is bp.BuildStatus.COMPILE_FAILED for run in failed.runs))
    check("failed-compile-classification", failed.classification is bp.BuildReproducibility.NOT_ESTABLISHED)

    if baseline_manifest is not None and baseline_manifest.build_status is bp.BuildStatus.OK:
        expect_fail(
            "overstrong-reproducibility-claim",
            lambda: bp.BuildComparison(
                runs=comparison.runs,
                source_reproducible=True,
                manifest_reproducible=True,
                object_reproducible=True,
                executable_reproducible=False,
                classification=bp.BuildReproducibility.EXECUTABLE_REPRODUCIBLE,
                toolchain_available=True,
            ),
        )
    else:
        print("SKIP: overstrong-reproducibility-claim (toolchain unavailable)")

    expect_fail(
        "single-run-comparison",
        lambda: bp.compare_runs([failed.runs[0]], toolchain_available=False),
    )

    expect_fail("artifact-present-without-hash", lambda: bp.BuildArtifact("a.obj", bp.BuildArtifactKind.OBJECT, None, True))
    check("artifact-absent-allowed", bp.BuildArtifact("a.obj", bp.BuildArtifactKind.OBJECT, None, False).present is False)

    # L. no P2-10 implementation --------------------------------------------
    import ast as _ast

    module_source = Path(bp.__file__).read_text(encoding="utf-8")
    tree = _ast.parse(module_source)
    imported: set[str] = set()
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, _ast.ImportFrom):
            imported.add(node.module or "")
    defined = {
        node.name
        for node in _ast.walk(tree)
        if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef, _ast.ClassDef))
    }
    for token in ("executor", "mips", "emulator", "reference", "equivalence"):
        check(f"no-p2-10-import:{token}", not any(token in name.lower() for name in imported))
    for token in ("equivalence", "end_to_end", "execute_guest", "mips", "recompile"):
        check(f"no-p2-10-symbol:{token}", not any(token in name.lower() for name in defined))
    check("manifest-schema-no-forbidden", "timestamp" not in bp._canonical_json(baseline_document).lower())

    # M. P2-08 runtime compatibility ----------------------------------------
    check("runtime-abi-version-unchanged", rt.RUNTIME_ABI_VERSION == "1.0.0")
    check("runtime-abi-config-still-works", rt.RuntimeAbiConfig(services=service_table()).version.version_string == "1.0.0")

    # N. manifest artifact for evidence -------------------------------------
    if args.manifest_out and baseline_manifest is not None and baseline_manifest.build_status is bp.BuildStatus.OK:
        out = Path(args.manifest_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(baseline_manifest.serialize())

    tests = sum(1 for item in RESULTS if item["status"] == "PASS")
    if args.json:
        record = {
            "stage": "P2-09",
            "marker": f"OPENRECOMP_DETERMINISTIC_BUILD_V1=PASS tests={tests}",
            "tests": tests,
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "toolchain_available": compiler_available,
            "toolchain": toolchain.to_document() if toolchain else None,
            "classification": comparison.classification.value if comparison else None,
            "results": sorted(RESULTS, key=lambda item: item["check"]),
            "source_reproducible": comparison.source_reproducible if comparison else None,
            "manifest_reproducible": comparison.manifest_reproducible if comparison else None,
            "object_reproducible": comparison.object_reproducible if comparison else None,
            "executable_reproducible": comparison.executable_reproducible if comparison else None,
            "sample_hashes": {
                "generated.c": emit_host_translation(
                    host_call_program(),
                    host_call_classification(host_call_program()),
                    config=HostEmitterConfig(semantics=host_call_rules(), entry_function="fn_1000", runtime_abi=rt.RuntimeAbiConfig(services=service_table())),
                ).fingerprint(),
            } if compiler_available else {},
        }
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"OPENRECOMP_DETERMINISTIC_BUILD_V1_JSON={out.name}")

    if args.evidence_dir:
        if comparison is None:
            raise AssertionError("evidence generation requires a completed build comparison")
        write_evidence(
            Path(args.evidence_dir),
            comparison,
            toolchain,
            object_timestamps,
            exe_timestamps,
            EXPECTED_SMOKE,
        )

    print(f"OPENRECOMP_DETERMINISTIC_BUILD_V1=PASS tests={tests}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
