#!/usr/bin/env python3
"""OpenRecomp Phase-8 evidence closure gate (P8-12).

P8-12 re-runs the bounded public MIPS32 path from clean inputs and verifies
the complete evidence chain:

* frozen fixture identity;
* analysis-cache correctness under the immutable-hash key contract;
* generated-source identity (all four emission files);
* native result identity (executable and observable record);
* independent reference equivalence;
* workflow reproducibility;
* source manifest, stage evidence records and control-plane consistency;
* zero implementation delta for this stage.

On success it emits::

    OPENRECOMP_P8_12=PASS
    OPENRECOMP_PHASE8_EVIDENCE_CLOSURE_V1=PASS tests=<count>
    OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase8_evidence_closure_v1.py
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
import p8_analysis_cache_v1 as analysis_cache  # noqa: E402
import p8_workflow_v1 as workflow  # noqa: E402

EVIDENCE_DIR = ROOT / ".openrecomp-phase8" / "evidence" / "P8-12"
WORKSPACE = ROOT / ".openrecomp-phase8" / "build" / "P8-12"

STAGE = "P8-12"
STAGE_MARKER = "OPENRECOMP_P8_12"
FEATURE_MARKER = "OPENRECOMP_PHASE8_EVIDENCE_CLOSURE_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY"
NOT_PROVEN = "NOT_PROVEN"

FIXTURE_ELF = ROOT / ".openrecomp-phase8" / "build" / "P8-01" / "candidate-a" / "p8_aes128_mips32_O1.elf"
FIXTURE_SHA256 = "0a90f47754f6331b868ec09ad23c451fc2c73925a43897fa62a696b0d40dde65"
EXPECTED_EMISSION = {
    "program.c": ("3df423e0efdd1b6d0c91ce9f95bd33d0b58f08833226314bd43aff407751c704", 97830),
    "p8_image_v1.c": ("d5d95845cf6574b7791996bdacd4d1f6994359c9e6c6911e71f1e006fb9b6d8d", 166198),
    "p8_runtime_support.c": ("9b5e70f524741612fc25a2def189fe436c757ceb4e064daa3c4f76088b9595c5", 7662),
    "p8_driver.c": ("e918de647ed34d9eaf451b93beb6b4f490676484c737484b7d8602f500f2ecea", 4172),
}
EXPECTED_EXECUTABLE_SHA256 = "fb98c8a68c5c3af7bc30dab2e907910e1c1dfd665eb79e0ee7fcd60dd07a04dc"
EXPECTED_OBSERVABLE = {
    "exit_status": "0x00000000",
    "registers_digest": "0x7ee0f4a187050726",
    "memory_digest": "0x231c4a49e79c5e56",
    "transcript_len": 33,
    "transcript_digest": "0xca6dcb87f8ac9814",
    "reads": 1136,
    "writes": 681,
    "host_calls": 33,
    "denied": 0,
}
STAGES = tuple(f"P8-{index:02d}" for index in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11))

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


def main() -> int:
    try:
        data = FIXTURE_ELF.read_bytes()
        check("fixture:sha256", sha256_bytes(data) == FIXTURE_SHA256, sha256_bytes(data))

        # source manifest and control plane
        manifest = ROOT / ".openrecomp-phase8" / "SOURCE_SHA256SUMS.txt"
        manifest_run = None
        import subprocess

        manifest_run = subprocess.run(
            [sys.executable, str(ROOT / ".openrecomp-phase8" / "src" / "p8_source_manifest_v1.py")],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        check("manifest:verifies", manifest_run.returncode == 0 and "=PASS entries=" in manifest_run.stdout, "phase-8 source manifest verified")
        state = (ROOT / ".openrecomp-phase8" / "STATE.md").read_text(encoding="utf-8")
        check("state:queue-frozen", "QUEUE_FREEZE=FROZEN" in state, "FROZEN")
        terminal_ok = f"{TERMINAL_MARKER}={NOT_PROVEN}" in state or (
            f"{TERMINAL_MARKER}=PASS" in state
            and "FINAL_VERDICT=PASS" in state
            and "STATUS=COMPLETE" in state
        )
        check("state:terminal-reserved", terminal_ok, "reserved or consistently promoted")
        check("state:general-permanent", f"{GENERAL_MARKER}={NOT_PROVEN}" in state, NOT_PROVEN)
        for stage in STAGES:
            check(f"ledger:{stage}", "| " + stage in state, stage)

        # stage evidence records: run captures and sidecar hashes
        evidence_root = ROOT / ".openrecomp-phase8" / "evidence"
        verified_runs = 0
        verified_sidecars = 0
        for stage in STAGES:
            stage_dir = evidence_root / stage
            check(f"evidence:{stage}:result", (stage_dir / "RESULT.md").is_file(), stage)
            runs_path = stage_dir / "official_runs.json"
            check(f"evidence:{stage}:official-runs", runs_path.is_file(), stage)
            runs = json.loads(runs_path.read_text(encoding="utf-8"))
            for run in runs["runs"]:
                stdout_path = stage_dir / run["stdout_file"]
                stderr_path = stage_dir / run["stderr_file"]
                check(
                    f"evidence:{stage}:{run['name']}:stdout",
                    stdout_path.is_file()
                    and sha256_bytes(stdout_path.read_bytes()) == run["stdout_sha256_raw"]
                    and len(stdout_path.read_bytes()) == run["stdout_bytes"],
                    run["stdout_sha256_raw"],
                )
                check(
                    f"evidence:{stage}:{run['name']}:stderr",
                    stderr_path.is_file()
                    and sha256_bytes(stderr_path.read_bytes()) == run["stderr_sha256"]
                    and len(stderr_path.read_bytes()) == run["stderr_bytes"],
                    run["stderr_sha256"],
                )
                verified_runs += 1
            for name, digest in sorted(runs.get("sidecars", {}).items()):
                path = stage_dir / name
                check(f"evidence:{stage}:sidecar:{name}", path.is_file() and sha256_bytes(path.read_bytes()) == digest, digest)
                verified_sidecars += 1

        # analysis-cache correctness with a real product
        cache = analysis_cache.AnalysisCache(WORKSPACE / "cache", "P8-12")
        ingested = elf.ingest(data, target.MIPS32_O32)
        region = ingested.parsed.executable_regions()[0]
        analysis = frontier.analyze(ingested.image.read_u32, region.p_vaddr, region.p_vaddr + region.p_memsz, ingested.parsed.header.e_entry)
        key_inputs = {
            "product": "frontier-summary",
            "input_sha256": FIXTURE_SHA256,
            "input_size_bytes": len(data),
            "analysis_config": {"entry": ingested.parsed.header.e_entry, "text_size": region.p_memsz},
            "frontend_sha256": {
                ".openrecomp-phase3/src/p3_elf_image_v1.py": sha256_bytes((ROOT / ".openrecomp-phase3" / "src" / "p3_elf_image_v1.py").read_bytes()),
                ".openrecomp-phase3/src/p3_code_frontier_v1.py": sha256_bytes((ROOT / ".openrecomp-phase3" / "src" / "p3_code_frontier_v1.py").read_bytes()),
            },
            "semantic_model": {"program_model": "1.0.0"},
            "producer_sha256": sha256_bytes((ROOT / ".openrecomp-phase8" / "src" / "p8_workflow_v1.py").read_bytes()),
        }
        payload = {"summary": analysis["summary"], "entry": ingested.parsed.header.e_entry}
        cache.put(key_inputs, payload)
        check("analysis-cache:hit", cache.get(key_inputs) == payload, "same key")
        check("analysis-cache:miss-on-different-fixture", cache.get({**key_inputs, "input_sha256": "0" * 64}) is None, "different fixture")
        check("analysis-cache:miss-on-different-config", cache.get({**key_inputs, "analysis_config": {"entry": 0}}) is None, "different configuration")

        # clean re-run of the bounded path
        if WORKSPACE.exists():
            shutil.rmtree(WORKSPACE)
        WORKSPACE.mkdir(parents=True, exist_ok=True)
        result = workflow.run_workflow(FIXTURE_ELF, workspace=WORKSPACE / "clean")
        check("workflow:outcome", result["outcome"] == "COMPLETED", json.dumps(result, sort_keys=True)[:200])
        for name, (digest, size) in sorted(EXPECTED_EMISSION.items()):
            observed = next(item for item in result["emission"]["files"] if item["name"] == name)
            check(f"emission:{name}", observed["sha256"] == digest and observed["bytes"] == size, json.dumps(observed, sort_keys=True))
        check("native:executable-identity", result["build"]["executable_sha256"] == EXPECTED_EXECUTABLE_SHA256, result["build"]["executable_sha256"])
        check("native:classification", result["build"]["classification"] == "EXECUTABLE_REPRODUCIBLE", result["build"]["classification"])
        native_values = {
            "exit_status": result["native"]["exit_status"],
            "registers_digest": result["native"]["registers_digest"],
            "memory_digest": result["native"]["memory"],
            "transcript_len": result["native"]["transcript_len"],
            "transcript_digest": result["native"]["transcript"],
            "reads": result["native"]["reads"],
            "writes": result["native"]["writes"],
            "host_calls": result["native"]["host_calls"],
            "denied": result["native"]["denied"],
        }
        check("native:observable-identity", native_values == EXPECTED_OBSERVABLE, json.dumps(native_values, sort_keys=True))
        check("reference:equivalence", result["equivalence"] == {"excluded_observables": [], "mismatches": {}}, json.dumps(result["equivalence"], sort_keys=True))
        reference_values = {
            "exit_status": result["reference"]["exit_status"],
            "registers_digest": result["reference"]["registers_digest"],
            "memory_digest": result["reference"]["memory_digest"],
            "transcript_len": result["reference"]["transcript_len"],
            "transcript_digest": result["reference"]["transcript_digest"],
            "reads": result["reference"]["reads"],
            "writes": result["reference"]["writes"],
            "host_calls": result["reference"]["host_calls"],
            "denied": result["reference"]["denied"],
        }
        check("reference:observable-identity", reference_values == EXPECTED_OBSERVABLE, json.dumps(reference_values, sort_keys=True))
        repeat = workflow.run_workflow(FIXTURE_ELF, workspace=WORKSPACE / "clean-repeat")
        check("workflow:reproducible", repeat == result, "identical record from clean inputs")

        write_evidence(
            "closure.json",
            {
                "stage": STAGE,
                "fixture": {"sha256": FIXTURE_SHA256},
                "implementation_delta": "none",
                "verified_runs": verified_runs,
                "verified_sidecars": verified_sidecars,
                "analysis_cache": cache.stats(),
                "workflow": {
                    "outcome": result["outcome"],
                    "emission_fingerprint": result["emission"]["program_fingerprint"],
                    "executable_sha256": result["build"]["executable_sha256"],
                    "native": EXPECTED_OBSERVABLE,
                    "reference": reference_values,
                    "excluded_observables": [],
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
        "stage_name": "Phase-8 evidence closure",
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
    write_evidence("p8_12_tests.json", record)

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
