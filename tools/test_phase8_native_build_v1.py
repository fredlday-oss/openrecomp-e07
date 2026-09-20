#!/usr/bin/env python3
"""OpenRecomp Phase-8 incremental native build gate (P8-07).

P8-07 compiles the P8-06 emission set through the existing host-native
toolchain/runtime boundary (`openrecomp.build_pipeline`, `clang-cl` +
`lld-link`, `/Brepro`):

* deterministic build inputs (the four content-hashed emission files);
* warnings treated as failure in the incremental path and recorded as empty
  compiler/linker stderr in the clean path;
* explicit toolchain provenance;
* incremental content-hash reuse demonstrated (cold build compiles, warm
  build reuses every object byte-for-byte);
* one clean audited build path (two isolated runs,
  `EXECUTABLE_REPRODUCIBLE`) recorded for terminal verification;
* no embedded material beyond the permitted fixture image data.

On success it emits::

    OPENRECOMP_P8_07=PASS
    OPENRECOMP_PHASE8_NATIVE_BUILD_V1=PASS tests=<count>
    OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase8_native_build_v1.py
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
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
import p8_incremental_build_v1 as incremental  # noqa: E402
import p8_memory_contract_v1 as contract_v1  # noqa: E402
import p8_structure_v1 as structure_bridge  # noqa: E402
from openrecomp import build_pipeline as bp  # noqa: E402
from openrecomp.program_model import ProgramSource  # noqa: E402

EVIDENCE_DIR = ROOT / ".openrecomp-phase8" / "evidence" / "P8-07"
WORKSPACE = ROOT / ".openrecomp-phase8" / "build" / "P8-07"
INCREMENTAL_DIR = WORKSPACE / "incremental"
CACHE_DIR = ROOT / ".openrecomp-phase8" / "build" / "cache" / "P8-07"
CLEAN_DIR = WORKSPACE / "clean"

STAGE = "P8-07"
STAGE_MARKER = "OPENRECOMP_P8_07"
FEATURE_MARKER = "OPENRECOMP_PHASE8_NATIVE_BUILD_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY"
NOT_PROVEN = "NOT_PROVEN"

FIXTURE_ELF = ROOT / ".openrecomp-phase8" / "build" / "P8-01" / "candidate-a" / "p8_aes128_mips32_O1.elf"
FIXTURE_SHA256 = "0a90f47754f6331b868ec09ad23c451fc2c73925a43897fa62a696b0d40dde65"
EXPECTED_PROGRAM_FINGERPRINT = "3df423e0efdd1b6d0c91ce9f95bd33d0b58f08833226314bd43aff407751c704"
EXPECTED_EMISSION_HASHES = {
    "program.c": "3df423e0efdd1b6d0c91ce9f95bd33d0b58f08833226314bd43aff407751c704",
    "p8_image_v1.c": "d5d95845cf6574b7791996bdacd4d1f6994359c9e6c6911e71f1e006fb9b6d8d",
    "p8_runtime_support.c": "9b5e70f524741612fc25a2def189fe436c757ceb4e064daa3c4f76088b9595c5",
    "p8_driver.c": "e918de647ed34d9eaf451b93beb6b4f490676484c737484b7d8602f500f2ecea",
}
SUPPORT_SOURCE = ROOT / ".openrecomp-phase8" / "runtime" / "p8_runtime_support.c"
DRIVER_SOURCE = ROOT / ".openrecomp-phase8" / "runtime" / "p8_observable_driver.c"

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


def build_set():
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


def main() -> int:
    try:
        data = FIXTURE_ELF.read_bytes()
        check("fixture:sha256", sha256_bytes(data) == FIXTURE_SHA256, sha256_bytes(data))
        build = build_set()
        for name, expected in sorted(EXPECTED_EMISSION_HASHES.items()):
            check(f"emission:{name}", build["hashes"][name] == expected, build["hashes"][name])
        check("emission:program-continuity", build["program_fingerprint"] == EXPECTED_PROGRAM_FINGERPRINT, build["program_fingerprint"])

        toolchain = bp.discover_toolchain()
        check("toolchain:available", toolchain is not None, "clang-cl + lld-link")
        check(
            "toolchain:identity",
            toolchain.compiler.identity == "clang-cl.exe" and toolchain.linker.identity == "lld-link.exe",
            f"{toolchain.compiler.identity} + {toolchain.linker.identity}",
        )
        check("toolchain:version-recorded", bool(toolchain.compiler.version) and bool(toolchain.linker.version), toolchain.compiler.version)

        if WORKSPACE.exists():
            shutil.rmtree(WORKSPACE)
        if CACHE_DIR.exists():
            shutil.rmtree(CACHE_DIR)
        WORKSPACE.mkdir(parents=True, exist_ok=True)

        # Use the audited pipeline's source names so the incremental path is
        # byte-comparable with the clean path.
        pipeline_files = {
            "generated.c": build["files"]["program.c"],
            "p8_image_v1.c": build["files"]["p8_image_v1.c"],
            "p8_runtime_support.c": build["files"]["p8_runtime_support.c"],
            "p8_driver.c": build["files"]["p8_driver.c"],
        }
        builder = incremental.IncrementalBuilder(INCREMENTAL_DIR, CACHE_DIR, toolchain)
        cold = builder.build(pipeline_files)
        check("incremental:cold-compiles-all", cold["compiled"] == 4 and cold["reused"] == 0, json.dumps({"compiled": cold["compiled"], "reused": cold["reused"]}))
        warm = builder.build(pipeline_files)
        check("incremental:warm-reuses-all", warm["compiled"] == 0 and warm["reused"] == 4, json.dumps({"compiled": warm["compiled"], "reused": warm["reused"]}))
        check("incremental:executable-stable", cold["executable_sha256"] == warm["executable_sha256"], cold["executable_sha256"])
        check(
            "incremental:object-keys-content-addressed",
            all(len(record["key"]) == 64 for record in warm["records"]) and len({record["key"] for record in warm["records"]}) == 4,
            "content-addressed",
        )
        corrupted_key = warm["records"][0]["key"]
        (CACHE_DIR / f"{corrupted_key}.obj").write_bytes(b"corrupt")
        corrupted = builder.build(pipeline_files)
        check(
            "incremental:corrupt-cache-recompiles",
            corrupted["compiled"] == 1 and corrupted["reused"] == 3,
            json.dumps({"compiled": corrupted["compiled"], "reused": corrupted["reused"]}),
        )
        check("incremental:executable-unchanged-after-repair", corrupted["executable_sha256"] == cold["executable_sha256"], corrupted["executable_sha256"])

        clean = bp.build_generated_host(
            lambda: build["files"]["program.c"],
            support_sources=(
                bp.BuildSource("p8_image_v1.c", bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE, build["files"]["p8_image_v1.c"].encode("utf-8")),
                bp.BuildSource("p8_runtime_support.c", bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE, build["files"]["p8_runtime_support.c"].encode("utf-8")),
                bp.BuildSource("p8_driver.c", bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE, build["files"]["p8_driver.c"].encode("utf-8")),
            ),
            config=bp.BuildConfig(fixture_id="p8-07-mips32-native-build", smoke_test=False, run_count=2),
            workspace=CLEAN_DIR,
            keep_workspace=True,
        )
        check("clean:status-ok", all(run.manifest.build_status is bp.BuildStatus.OK for run in clean.runs), "ok")
        check("clean:executable-reproducible", clean.classification is bp.BuildReproducibility.EXECUTABLE_REPRODUCIBLE, clean.classification.value)
        check("clean:executables-identical", clean.runs[0].manifest.outputs[-1].sha256 == clean.runs[1].manifest.outputs[-1].sha256, clean.runs[0].manifest.outputs[-1].sha256)
        clean_executable = CLEAN_DIR / "run1" / "program.exe"
        clean_objects = {
            record["object"]: record
            for record in (
                {
                    "object": pathlib.Path(item.name).stem + ".obj",
                    "sha256": item.sha256,
                }
                for item in clean.runs[0].manifest.outputs
                if item.kind is bp.BuildArtifactKind.OBJECT
            )
        }
        check(
            "clean:objects-match-incremental",
            all(
                clean_objects[record["object"]]["sha256"] == record["object_sha256"]
                for record in cold["records"]
            ),
            json.dumps({record["object"]: record["object_sha256"] for record in cold["records"]}, sort_keys=True),
        )
        check(
            "clean:executable-size-matches-incremental",
            len(clean_executable.read_bytes()) == cold["executable_bytes"],
            f"{len(clean_executable.read_bytes())} vs {cold['executable_bytes']}",
        )
        check(
            "clean:manifest-inputs",
            [item.name for item in clean.runs[0].manifest.inputs] == ["generated.c", "p8_driver.c", "p8_image_v1.c", "p8_runtime_support.c"],
            json.dumps([item.name for item in clean.runs[0].manifest.inputs]),
        )
        documented_warning = "-Wparentheses-equality"
        check(
            "warnings:documented-only",
            all(
                all(documented_warning in line for line in (run.get("warnings") or []))
                for run in (cold, warm, corrupted)
            ),
            json.dumps({"cold_warnings": len(cold["warnings"]), "warm_warnings": len(warm["warnings"])}),
        )
        check(
            "clean:warnings-documented-only",
            all(
                all(
                    documented_warning in line
                    for line in (run.compiler_stderr or "").splitlines()
                    if "warning:" in line
                )
                for run in clean.runs
            ),
            json.dumps([sum(1 for line in (run.compiler_stderr or "").splitlines() if "warning:" in line) for run in clean.runs]),
        )
        check("clean:brepro-flags", all("/Brepro" in command for run in clean.runs for command in run.manifest.compile_commands), "deterministic flags")

        write_evidence(
            "native_build.json",
            {
                "stage": STAGE,
                "fixture": {"sha256": FIXTURE_SHA256},
                "emission_hashes": build["hashes"],
                "toolchain": {
                    "compiler": toolchain.compiler.identity,
                    "compiler_version": toolchain.compiler.version,
                    "linker": toolchain.linker.identity,
                    "linker_version": toolchain.linker.version,
                    "compile_arguments": list(toolchain.compile_arguments),
                    "link_arguments": list(toolchain.link_arguments),
                },
                "incremental": {
                    "cold": {"compiled": cold["compiled"], "reused": cold["reused"], "executable_sha256": cold["executable_sha256"]},
                    "warm": {"compiled": warm["compiled"], "reused": warm["reused"], "executable_sha256": warm["executable_sha256"]},
                    "corrupt_cache": {"compiled": corrupted["compiled"], "reused": corrupted["reused"], "executable_sha256": corrupted["executable_sha256"]},
                    "cache_entries": cold["cache_entries"],
                },
                "clean_build": {
                    "classification": clean.classification.value,
                    "executable_sha256": sha256_bytes(clean_executable.read_bytes()),
                    "executable_bytes": len(clean_executable.read_bytes()),
                    "manifest_inputs": [item.name for item in clean.runs[0].manifest.inputs],
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
        "stage_name": "Incremental native build",
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
    write_evidence("p8_07_tests.json", record)

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
