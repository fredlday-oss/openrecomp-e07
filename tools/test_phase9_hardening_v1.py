#!/usr/bin/env python3
"""OpenRecomp Phase-9 hardening and reproducibility gate (P9-12).

The gate proves the bounded Phase-9 path is fail-closed and reproducible:

* a bounded workflow with explicit failure categories completes the public
  fixture end to end (classification, analysis, structure, closure, memory
  contract, emission, native build, execution, reference equivalence);
* malformed/unsupported inputs are rejected deterministically before any
  emission, build or execution with stable categories (bad container,
  unresolved indirect control flow, uncovered semantics, memory-map
  violations, unknown GPU/SPU/CD-ROM commands, unknown BIOS services);
* the immutable-hash analysis cache rejects stale and corrupted entries;
* a clean rebuild in a fresh workspace reproduces the P9-10 executable and
  observable identities exactly, twice;
* the Phase-9 source manifest, the frozen Phase-8 manifest and the frozen
  Phase-3 module hashes re-verify;
* every committed Phase-9 evidence text file passes the public-safety scan
  (no private payload bytes, no private ASCII runs, no absolute host paths).

On success it emits::

    OPENRECOMP_P9_12=PASS
    OPENRECOMP_PHASE9_HARDENING_V1=PASS tests=<count>
    OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN
    OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN

Usage:

    python tools/test_phase9_hardening_v1.py
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / ".openrecomp-phase3" / "src"))
sys.path.insert(0, str(ROOT / ".openrecomp-phase8" / "src"))
sys.path.insert(0, str(ROOT / ".openrecomp-phase9" / "src"))
sys.path.insert(0, str(ROOT / ".openrecomp-phase9" / "fixture"))

import p9_analysis_cache_v1 as cache_v1  # noqa: E402
import p9_bios_boundary_v1 as bios  # noqa: E402
import p9_cdrom_boundary_v1 as cdrom  # noqa: E402
import p9_emission_v1 as emission  # noqa: E402
import p9_gpu_boundary_v1 as gpu  # noqa: E402
import p9_image_bridge_v1 as bridge  # noqa: E402
import p9_memory_map_v1 as memory_map  # noqa: E402
import p9_psx_exe_v1 as psx  # noqa: E402
import p9_public_fixture_v1 as fixture  # noqa: E402
import p9_reference_psx_v1 as reference  # noqa: E402
import p9_semantics_v1 as semantics  # noqa: E402
import p9_spu_boundary_v1 as spu  # noqa: E402
import psx_fixture_builder_v1 as builder  # noqa: E402
from openrecomp import build_pipeline as bp  # noqa: E402
from openrecomp.host_emitter import HostEmitterError, emit_host_translation  # noqa: E402

STAGE = "P9-12"
FEATURE_MARKER = "OPENRECOMP_PHASE9_HARDENING_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE9_HERCULES_PLAYABILITY"
NOT_PROVEN = "NOT_PROVEN"

SUPPORT_SOURCE = ROOT / ".openrecomp-phase9" / "runtime" / "p9_runtime_support.c"
DRIVER_SOURCE = ROOT / ".openrecomp-phase9" / "runtime" / "p9_observable_driver.c"
CACHE_DIR = ROOT / ".openrecomp-phase9" / "cache" / "P9-12"
WORKSPACE = ROOT / ".openrecomp-phase9" / "build" / "P9-12"
DEFAULT_PRIVATE_FIXTURE = (
    ROOT.parents[1] / "fixtures" / "psx" / "hercules" / "SLUS_005.29"
)

P9_10_EXECUTABLE = "5c016be2f043760ef6ac1a7c37c60bbe335c271f307b8e05275f75e0ee2ceb9d"
P9_10_OBSERVABLE = {
    "failed": 0,
    "error": "",
    "exit_status": "0x00000002",
    "registers_digest": "0x17f2292e1363f17f",
    "memory_digest": "0x28d892afac2d8496",
    "gpu_events": 2,
    "gpu_digest": "0x6a326cbc723c24b1",
    "input_events": 2,
    "input_digest": "0xe35ba7548adde99a",
    "spu_events": 1,
    "spu_digest": "0x55788edbf95cf3ea",
    "cdrom_events": 1,
    "cdrom_digest": "0x0dc54fdf2d1b3c3c",
    "reads": 1,
    "writes": 4,
    "denied": 0,
    "host_calls": 0,
}

FROZEN_P3_MODULES = {
    ".openrecomp-phase3/src/p3_code_frontier_v1.py": "f02c4e7507087e052f1a899ef67d87f8ed82ecc4954e8214ccea922a2e361d71",
    ".openrecomp-phase3/src/p3_decode_mips32_v1.py": "c808a23afad5771a42f3f7eee9450b84fc6131d0416961a3ed8e78a9f5126b0b",
    ".openrecomp-phase8/src/p8_structure_v1.py": "24109660cfa1876b9ffabe141374d1a1b26c74d6fc0f68260bfb440617077a1b",
}

HOST_PATH_RE = re.compile(r"(?:[A-Za-z]:\\|/home/|/Users/|/root/)")


class WorkflowFailure(RuntimeError):
    """Bounded workflow fail-closed category."""

    def __init__(self, category: str, stage: str, detail: str = "") -> None:
        super().__init__(f"{category}@{stage}: {detail}")
        self.category = category
        self.stage = stage
        self.detail = detail


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


def expect_failure(label: str, function, expected_category: str) -> None:
    try:
        function()
    except WorkflowFailure as exc:
        check(label, exc.category == expected_category, f"expected {expected_category} got {exc.category}")
        return
    check(label, False, f"expected {expected_category} but the workflow succeeded")


def bounded_workflow(data: bytes, *, workspace: pathlib.Path, do_build: bool = True, do_execute: bool = True):
    """A bounded P9 workflow with explicit fail-closed categories."""
    try:
        image = psx.ingest(data)
    except psx.PsxExeError as exc:
        raise WorkflowFailure("UNSUPPORTED_PSX_CONTAINER", "ingestion", exc.code) from exc
    try:
        contract = memory_map.build_contract(image)
    except memory_map.MemoryMapError as exc:
        raise WorkflowFailure("UNSUPPORTED_MEMORY_RUNTIME", "memory-map", exc.code) from exc
    flat = memory_map.flat_image(image)
    pipeline = bridge.analyze(image, contract, flat)
    if pipeline.structure_error is not None:
        category = (
            "UNRESOLVED_INDIRECT_CONTROL_FLOW"
            if pipeline.structure_error["code"] in ("CONTROL_DELAY_SLOT_UNKNOWN", "UNSUPPORTED_CONTROL_TRANSFER")
            else "UNSUPPORTED_ISA_SEMANTIC"
        )
        raise WorkflowFailure(category, "structure", pipeline.structure_error["code"])
    if pipeline.structure_summary["unresolved_sites"]:
        raise WorkflowFailure("UNRESOLVED_INDIRECT_CONTROL_FLOW", "structure", "unresolved sites")
    closure = semantics.coverage(pipeline.structure)
    if not closure["closed"]:
        raise WorkflowFailure("UNSUPPORTED_ISA_SEMANTIC", "closure", json.dumps(closure["uncovered"])[:200])
    build_set = emission.build_build_set(
        pipeline.structure,
        contract,
        flat,
        SUPPORT_SOURCE.read_text(encoding="utf-8"),
        DRIVER_SOURCE.read_text(encoding="utf-8"),
        sha256(data),
    )
    if not do_build:
        return {"outcome": "COMPLETED", "stage": "emission", "build_set": build_set, "pipeline": pipeline}
    if workspace.exists():
        shutil.rmtree(workspace)
    comparison = bp.build_generated_host(
        lambda: build_set["files"][emission.PROGRAM_NAME],
        support_sources=(
            bp.BuildSource(emission.IMAGE_NAME, bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE, build_set["files"][emission.IMAGE_NAME].encode("utf-8")),
            bp.BuildSource(emission.SUPPORT_NAME, bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE, build_set["files"][emission.SUPPORT_NAME].encode("utf-8")),
            bp.BuildSource(emission.DRIVER_NAME, bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE, build_set["files"][emission.DRIVER_NAME].encode("utf-8")),
        ),
        config=bp.BuildConfig(fixture_id="p9-12-workflow", smoke_test=False, run_count=2),
        workspace=workspace,
        keep_workspace=True,
    )
    if any(run.manifest.build_status is not bp.BuildStatus.OK for run in comparison.runs):
        raise WorkflowFailure("BUILD_FAILURE", "native-build", "build status not OK")
    if not do_execute:
        return {"outcome": "COMPLETED", "stage": "build", "build_set": build_set, "pipeline": pipeline}
    executable = workspace / "run1" / "program.exe"
    completed = subprocess.run([str(executable)], capture_output=True, timeout=600)
    if completed.returncode != 0 or completed.stderr:
        raise WorkflowFailure("EXECUTION_FAILURE", "native-execution", completed.stderr[:120].decode("ascii", "replace"))
    return {
        "outcome": "COMPLETED",
        "stage": "execution",
        "build_set": build_set,
        "pipeline": pipeline,
        "executable_sha256": sha256(executable.read_bytes()),
        "stdout": completed.stdout,
    }


def parse_native(stdout: bytes) -> dict:
    parsed: dict = {"registers": {}}
    for line in stdout.decode("utf-8").splitlines():
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


def native_observable(parsed: dict) -> dict:
    return {
        "failed": parsed.get("failed"),
        "error": parsed.get("error"),
        "exit_status": parsed.get("exit_status"),
        "registers_digest": parsed.get("registers_digest"),
        "memory_digest": parsed.get("memory"),
        "gpu_events": parsed.get("gpu_events"),
        "gpu_digest": parsed.get("gpu"),
        "input_events": parsed.get("input_events"),
        "input_digest": parsed.get("input"),
        "spu_events": parsed.get("spu_events"),
        "spu_digest": parsed.get("spu"),
        "cdrom_events": parsed.get("cdrom_events"),
        "cdrom_digest": parsed.get("cdrom"),
        "reads": parsed.get("reads"),
        "writes": parsed.get("writes"),
        "denied": parsed.get("denied"),
        "host_calls": parsed.get("host_calls"),
    }


def scan_evidence(private_payload: bytes | None) -> dict:
    evidence_root = ROOT / ".openrecomp-phase9" / "evidence"
    files = sorted(path for path in evidence_root.rglob("*") if path.is_file())
    leaks: list[str] = []
    host_paths: list[str] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        relative = path.relative_to(ROOT).as_posix()
        if HOST_PATH_RE.search(text):
            host_paths.append(relative)
        if private_payload is not None:
            lowered = text.lower()
            if private_payload[:64].hex() in lowered:
                leaks.append(f"{relative}:hex")
            if base64.b64encode(private_payload[:48]).decode("ascii") in text:
                leaks.append(f"{relative}:base64")
            for start in range(0, min(len(private_payload), 512)):
                run = private_payload[start : start + 8]
                if len(run) == 8 and all(32 <= byte < 127 for byte in run):
                    if run.decode("ascii") in text:
                        leaks.append(f"{relative}:ascii")
                        break
    return {"files_scanned": len(files), "payload_leaks": leaks, "host_path_leaks": host_paths}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--evidence-dir",
        default=".openrecomp-phase9/evidence/P9-12",
        help="evidence directory relative to the repository root",
    )
    parser.add_argument(
        "--private-fixture",
        default=os.environ.get("OPENRECOMP_PSX_PRIVATE_FIXTURE", str(DEFAULT_PRIVATE_FIXTURE)),
        help="optional local path to the private Hercules fixture",
    )
    options = parser.parse_args()
    evidence = (ROOT / options.evidence_dir).resolve()

    try:
        # --- bounded workflow completes the public fixture ------------------
        public_bytes = fixture.build_fixture()
        result = bounded_workflow(public_bytes, workspace=WORKSPACE)
        check("workflow:completed", result["outcome"] == "COMPLETED" and result["stage"] == "execution", result["stage"])
        check("workflow:executable-identity", result["executable_sha256"] == P9_10_EXECUTABLE, result["executable_sha256"])
        native = parse_native(result["stdout"])
        observed = native_observable(native)
        check("workflow:observable-identity", observed == P9_10_OBSERVABLE, json.dumps(observed, sort_keys=True))
        second = bounded_workflow(public_bytes, workspace=WORKSPACE / "rebuild")
        check("workflow:rebuild-identity", second["executable_sha256"] == P9_10_EXECUTABLE, second["executable_sha256"])
        check("workflow:rebuild-stdout", second["stdout"] == result["stdout"], "byte-identical")
        run = reference.load_and_run(public_bytes)
        reference_observables = run.to_observables()
        mismatches = {
            key: {"native": observed[key], "reference": reference_observables[key]}
            for key in P9_10_OBSERVABLE
            if observed[key] != reference_observables[key]
        }
        check("workflow:reference-agreement", not mismatches, json.dumps(mismatches, sort_keys=True))

        # --- malformed / unsupported inputs fail closed ---------------------
        bad_magic = bytearray(public_bytes)
        bad_magic[0:4] = b"PS-Y"
        expect_failure("negative:bad-container", lambda: bounded_workflow(bytes(bad_magic), workspace=WORKSPACE), "UNSUPPORTED_PSX_CONTAINER")

        truncated = public_bytes[: 0x800 + 16]
        expect_failure("negative:truncated-container", lambda: bounded_workflow(truncated, workspace=WORKSPACE), "UNSUPPORTED_PSX_CONTAINER")

        unresolved_words = list(fixture.build_words())
        bad_index = len(unresolved_words)
        unresolved_words += [
            builder.r_type("jalr", rs=8, rd=31),
            builder.nop(),
            builder.r_type("jr", rs=31),
            builder.nop(),
        ]
        unresolved_words[fixture.helper_call_index()] = builder.j_type("jal", fixture.PROGRAM_LOAD_ADDRESS + 4 * bad_index)
        expect_failure(
            "negative:unresolved-indirect",
            lambda: bounded_workflow(builder.build_from_words(unresolved_words), workspace=WORKSPACE),
            "UNRESOLVED_INDIRECT_CONTROL_FLOW",
        )

        uncovered_words = list(fixture.build_words())
        bad_index = len(uncovered_words)
        uncovered_words += [
            builder.i_type("lwl", rs=8, rt=9, imm=1),
            builder.r_type("jr", rs=31),
            builder.nop(),
        ]
        uncovered_words[fixture.helper_call_index()] = builder.j_type("jal", fixture.PROGRAM_LOAD_ADDRESS + 4 * bad_index)
        expect_failure(
            "negative:uncovered-semantics",
            lambda: bounded_workflow(builder.build_from_words(uncovered_words), workspace=WORKSPACE),
            "UNSUPPORTED_ISA_SEMANTIC",
        )

        overlap_spec = builder.assemble_spec(
            tuple(0 for _ in range(0x400)), load_address=0x801FF000, stack_pointer=0x80200000
        )
        expect_failure(
            "negative:memory-map-overlap",
            lambda: bounded_workflow(builder.build(overlap_spec), workspace=WORKSPACE),
            "UNSUPPORTED_MEMORY_RUNTIME",
        )

        unknown_gpu = gpu.GpuAdapter().write(gpu.GP0_WRITE, 32, 0x10000000)
        check("negative:gpu-unknown-command", unknown_gpu["known"] is False and unknown_gpu["class"] == "UNKNOWN_COMMAND", json.dumps(unknown_gpu, sort_keys=True))
        unknown_spu = spu.SpuAdapter().write(0x1F801DC0, 16, 1)
        check("negative:spu-unknown-register", unknown_spu["blocker"] is True, json.dumps(unknown_spu, sort_keys=True))
        unknown_cdrom = cdrom.CdromAdapter().write(cdrom.COMMAND, 8, 0xFE)
        check("negative:cdrom-unknown-command", unknown_cdrom["blocker"] is True, json.dumps(unknown_cdrom, sort_keys=True))
        try:
            bios.default_boundary().invoke("bios-A0", ())
            check("negative:bios-unimplemented", False, "expected UNIMPLEMENTED_SERVICE")
        except bios.ServiceBoundaryError as exc:
            check("negative:bios-unimplemented", exc.code == "UNIMPLEMENTED_SERVICE", exc.code)

        negatives_record = {
            "schema": "openrecomp-phase9-hardening-negatives-v1",
            "stage": STAGE,
            "categories": [
                "UNSUPPORTED_PSX_CONTAINER",
                "UNSUPPORTED_MEMORY_RUNTIME",
                "UNRESOLVED_INDIRECT_CONTROL_FLOW",
                "UNSUPPORTED_ISA_SEMANTIC",
                "GPU_UNKNOWN_COMMAND_BLOCKER",
                "SPU_UNKNOWN_REGISTER_BLOCKER",
                "CDROM_UNKNOWN_COMMAND_BLOCKER",
                "BIOS_UNIMPLEMENTED_SERVICE",
            ],
        }
        write_json(evidence / "negatives.json", negatives_record)

        # --- immutable-hash cache -------------------------------------------
        if CACHE_DIR.exists():
            shutil.rmtree(CACHE_DIR)
        cache = cache_v1.AnalysisCache(CACHE_DIR)
        key_inputs = cache_v1.CacheKeyInputs(
            product="psx-exe-inventory",
            input_sha256=sha256(public_bytes),
            input_size_bytes=len(public_bytes),
            analysis_config={"bounded": True, "architecture": "mips32-bounded-v1"},
            frontend_sha256={"p9_psx_exe_v1.py": sha256((ROOT / ".openrecomp-phase9" / "src" / "p9_psx_exe_v1.py").read_bytes())},
            semantic_model={"rule_table": "1.0.0"},
            producer_sha256=sha256(pathlib.Path(__file__).read_bytes()),
        )
        product = {"entry": "0x80010000", "reachable_words": 48}
        cache.put(key_inputs, product)
        check("cache:round-trip", cache.get(key_inputs) == product, "round trip")
        stale = cache_v1.CacheKeyInputs(
            product="psx-exe-inventory",
            input_sha256="0" * 64,
            input_size_bytes=len(public_bytes),
            analysis_config={"bounded": True, "architecture": "mips32-bounded-v1"},
            frontend_sha256=key_inputs.frontend_sha256,
            semantic_model=key_inputs.semantic_model,
            producer_sha256=key_inputs.producer_sha256,
        )
        try:
            cache.get(stale)
            check("cache:stale-rejected", False, "expected CACHE_MISS")
        except cache_v1.CacheError as exc:
            check("cache:stale-rejected", exc.code == "CACHE_MISS", exc.code)
        corrupted_path = cache.path_for(key_inputs)
        corrupted = json.loads(corrupted_path.read_text(encoding="utf-8"))
        corrupted["product"]["reachable_words"] = 999
        corrupted_path.write_text(json.dumps(corrupted, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        try:
            cache.get(key_inputs)
            check("cache:corrupt-rejected", False, "expected CACHE_CORRUPT")
        except cache_v1.CacheError as exc:
            check("cache:corrupt-rejected", exc.code == "CACHE_CORRUPT", exc.code)
        cache.put(key_inputs, product)
        check("cache:repaired", cache.get(key_inputs) == product, "recomputed")
        write_json(
            evidence / "cache_test.json",
            {
                "schema": "openrecomp-phase9-cache-test-v1",
                "stage": STAGE,
                "cache_key": key_inputs.key(),
                "cache_schema": cache_v1.CACHE_SCHEMA,
                "stale_rejected": "CACHE_MISS",
                "corrupt_rejected": "CACHE_CORRUPT",
            },
        )

        # --- manifests and frozen modules -----------------------------------
        for rel, expected in sorted(FROZEN_P3_MODULES.items()):
            check(f"frozen:module:{rel}", sha256((ROOT / rel).read_bytes()) == expected, expected)
        manifest9 = subprocess.run([sys.executable, str(ROOT / ".openrecomp-phase9" / "src" / "p9_source_manifest_v1.py")], capture_output=True, text=True, encoding="utf-8")
        check("manifest:p9", manifest9.returncode == 0 and "=PASS entries=" in manifest9.stdout, manifest9.stdout.strip())
        manifest8 = subprocess.run([sys.executable, str(ROOT / ".openrecomp-phase8" / "src" / "p8_source_manifest_v1.py")], capture_output=True, text=True, encoding="utf-8")
        check("manifest:p8", manifest8.returncode == 0 and "=PASS entries=" in manifest8.stdout, manifest8.stdout.strip())

        # --- public-safety scan ---------------------------------------------
        fixture_path = pathlib.Path(options.private_fixture)
        private_payload = psx.ingest(fixture_path.read_bytes()).payload if fixture_path.is_file() else None
        scan = scan_evidence(private_payload)
        check("safety:no-payload-leaks", scan["payload_leaks"] == [], json.dumps(scan["payload_leaks"]))
        check("safety:no-host-paths", scan["host_path_leaks"] == [], json.dumps(scan["host_path_leaks"]))
        check("safety:files-scanned", scan["files_scanned"] >= 100, str(scan["files_scanned"]))
        write_json(evidence / "safety_scan.json", {"schema": "openrecomp-phase9-safety-scan-v1", "stage": STAGE, **scan})

        write_json(
            evidence / "rebuild.json",
            {
                "schema": "openrecomp-phase9-rebuild-v1",
                "stage": STAGE,
                "executable_sha256": result["executable_sha256"],
                "rebuild_executable_sha256": second["executable_sha256"],
                "observable": observed,
                "stdout_sha256": sha256(result["stdout"]),
                "reference_agreement": not mismatches,
            },
        )
    except AssertionError as exc:
        RESULTS.append({"check": "gate:assertion", "status": "FAIL", "detail": str(exc)})
    except Exception as exc:  # fail closed with a stable record
        RESULTS.append({"check": "gate:exception", "status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"})

    failed = [item for item in RESULTS if item["status"] == "FAIL"]
    status = "PASS" if not failed else "FAIL"
    results = sorted(RESULTS, key=lambda item: item["check"])
    record = {
        "stage": STAGE,
        "stage_name": "Hardening and reproducibility",
        "status": status,
        "tests": len(results),
        "passed": sum(1 for item in results if item["status"] == "PASS"),
        "failed": len(failed),
        "private_fixture": {
            "present": pathlib.Path(options.private_fixture).is_file(),
            "is_pass_criterion": False,
        },
        "checks": results,
        "failure": None if not failed else [item["check"] for item in failed],
    }
    write_json(evidence / "p9_12_tests.json", record)

    for item in results:
        print(f"{item['status']}: {item['check']}")
    print(f"OPENRECOMP_P9_12={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(results)}")
    print(f"{TERMINAL_MARKER}={NOT_PROVEN}")
    print(f"{GENERAL_MARKER}={NOT_PROVEN}")
    print(f"{PLAYABILITY_MARKER}={NOT_PROVEN}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
