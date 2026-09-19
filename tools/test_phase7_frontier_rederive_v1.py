#!/usr/bin/env python3
"""OpenRecomp Phase-7 TMNT frontier re-derivation gate (P7-01).

Re-derives the private TMNT compatibility frontier from scratch through the
frozen Phase-6 pipeline and workflow and requires exact equality with the
committed Phase-6 classifications: undocumented opcode `0x7C` at `0xC570`,
unresolved `$E2` indirect jumps at `0x86E8`/`0x8956`/`0x8F3C`, the
bank-window candidate frontier, no active mapper blocker and translation/
native progress still `NOT_ATTEMPTED`. No translation changes are made.

On success it emits::

    OPENRECOMP_P7_01=PASS
    OPENRECOMP_PHASE7_FRONTIER_REDERIVATION_V1=PASS tests=<count>
    OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN
    OPENRECOMP_PHASE7_TMMT_PLAYABILITY=NOT_PROVEN

Usage:

    python tools/test_phase7_frontier_rederive_v1.py \
        --evidence-dir .openrecomp-phase7/evidence/P7-01
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTROL7 = ROOT / ".openrecomp-phase7"
SRC7 = CONTROL7 / "src"
for entry in (str(ROOT), str(ROOT / "tools"),
              str(ROOT / ".openrecomp-phase5" / "src"),
              str(ROOT / ".openrecomp-phase6" / "src"), str(SRC7)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import p6_private_fixture_v1 as private_fixture  # noqa: E402
import p7_frontier_rederive_v1 as rederive_module  # noqa: E402

STAGE = "P7-01"
STAGE_MARKER = "OPENRECOMP_P7_01"
FEATURE_MARKER = "OPENRECOMP_PHASE7_FRONTIER_REDERIVATION_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE7_TMMT_PLAYABILITY"

P7_00_RECORD_REL = ".openrecomp-phase7/evidence/P7-00/p7_00_tests.json"
P7_00_GATE = "tools/test_phase7_boundary_v1.py"
P6_99_RECORD_REL = ".openrecomp-phase6/evidence/P6-99/p6_99_tests.json"
P6_99_RECORD_SHA256 = "e7e462f15ca64a2d8db130ec664ac309d5ebfef1c128fd392111d19e4be30ea4"

EXPECTED_ANCHORS = {
    rederive_module.P6_10_PIPELINE_REL:
        rederive_module.P6_10_PIPELINE_SHA256,
    rederive_module.P6_10_BLOCKERS_REL:
        rederive_module.P6_10_BLOCKERS_SHA256,
    rederive_module.P6_12_BLOCKERS_REL:
        rederive_module.P6_12_BLOCKERS_SHA256,
    rederive_module.P6_13_FRONTIER_REL:
        rederive_module.P6_13_FRONTIER_SHA256,
    rederive_module.P6_13_WORKFLOW_REL:
        rederive_module.P6_13_WORKFLOW_SHA256,
}

REGRESSIONS = (
    "tools/test_nes_rom_v1.py",
)

RESULTS: list[dict[str, str]] = []
FINDINGS: dict[str, Any] = {}
EVIDENCE_WRITES: dict[str, bytes] = {}


def check(label: str, condition: bool) -> None:
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL"})
        print(f"FAIL: {label}", flush=True)
        raise AssertionError(f"{label}: condition failed")
    RESULTS.append({"check": label, "status": "PASS"})
    print(f"PASS: {label}", flush=True)


def banner(name: str) -> None:
    print(f"\n--- {name} ---", flush=True)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical(document: Any) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True)
            + "\n").encode("utf-8")


def write_json(name: str, document: Any) -> None:
    EVIDENCE_WRITES[name] = canonical(document)


def read_json(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def run_regression(script: str, extra: list[str] | None = None) -> dict[str, Any]:
    command = [sys.executable, script, *(extra or [])]
    completed = subprocess.run(command, cwd=str(ROOT), capture_output=True)
    stdout = completed.stdout
    stderr = completed.stderr
    markers = [line for line in stdout.decode("utf-8", errors="replace").splitlines()
               if line.startswith("OPENRECOMP_")]
    return {
        "script": script,
        "command": ["python", script, *(extra or [])],
        "returncode": completed.returncode,
        "stdout_bytes": len(stdout),
        "stdout_sha256_raw": sha256_bytes(stdout),
        "stdout_sha256_lf": sha256_bytes(stdout.replace(b"\r\n", b"\n")),
        "stderr_bytes": len(stderr),
        "stderr_empty": not stderr,
        "markers": markers,
    }


def expect_rederive_fail(label: str, path: pathlib.Path) -> None:
    try:
        rederive_module.rederive(path=path, workspace=SCRATCH / "negative")
    except rederive_module.P7FrontierError:
        check(f"negative:{label}", True)
        return
    raise AssertionError(f"negative:{label}: accepted")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P7-01 TMNT frontier re-derivation gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase7/evidence/P7-01")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES, SCRATCH
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    SCRATCH = CONTROL7 / "scratch" / "P7-01"
    workspace = SCRATCH / "workspace"
    if workspace.exists():
        shutil.rmtree(workspace)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}

    print("=== P7-01 TMNT Frontier Re-derivation Gate ===", flush=True)
    failure: str | None = None
    try:
        banner("source_integrity")
        manifest = CONTROL7 / "SOURCE_SHA256SUMS.txt"
        entries = []
        for line in manifest.read_text(encoding="utf-8").strip().splitlines():
            digest, rel = line.split(" *", 1)
            entries.append((digest, rel))
        bad = [rel for digest, rel in entries
               if not (ROOT / rel).is_file() or sha256_file(ROOT / rel) != digest]
        check("source:manifest-verified", bool(entries) and not bad)

        banner("anchors")
        anchors = {}
        for rel, expected in EXPECTED_ANCHORS.items():
            path = ROOT / rel
            check(f"anchor:present:{rel}", path.is_file())
            actual = sha256_file(path)
            check(f"anchor:hash:{rel}", actual == expected)
            anchors[rel] = actual
        p7_00 = read_json(ROOT / P7_00_RECORD_REL)
        check("anchor:p7-00-record-pass",
              p7_00["status"] == "PASS" and p7_00["failure"] is None)
        check("anchor:p6-99-record",
              sha256_file(ROOT / P6_99_RECORD_REL) == P6_99_RECORD_SHA256)
        check("anchor:private-image",
              private_fixture.PRIVATE_ROM.is_file()
              and private_fixture.PRIVATE_ROM.stat().st_size
              == rederive_module.PRIVATE_SIZE
              and sha256_file(private_fixture.PRIVATE_ROM)
              == rederive_module.PRIVATE_IMAGE_SHA256)

        banner("control_plane")
        state = (CONTROL7 / "STATE.md").read_text(encoding="utf-8")
        queue = (CONTROL7 / "STAGE_QUEUE.md").read_text(encoding="utf-8")
        check("control-plane:stage-row", "| P7-01 |" in queue)
        check("control-plane:terminal-reserved",
              f"{TERMINAL_MARKER}=NOT_PROVEN" in queue
              and f"{TERMINAL_MARKER}=NOT_PROVEN" in state)
        check("control-plane:compat-reserved",
              f"{COMPAT_MARKER}=NOT_PROVEN" in queue
              and f"{COMPAT_MARKER}=NOT_PROVEN" in state)
        check("control-plane:playability-reserved",
              f"{PLAYABILITY_MARKER}=NOT_PROVEN" in queue
              and f"{PLAYABILITY_MARKER}=NOT_PROVEN" in state)
        check("control-plane:queue-freeze",
              "QUEUE_FREEZE=FROZEN" in state)

        banner("rederivation")
        record_a = rederive_module.rederive(workspace=workspace)
        record_b = rederive_module.rederive(workspace=workspace)
        check("rederive:deterministic",
              canonical(record_a) == canonical(record_b))
        check("rederive:comparisons",
              all(record_a["comparisons"].values()))
        check("rederive:digests-stable",
              record_a["pipeline_projection_sha256"]
              == record_b["pipeline_projection_sha256"]
              and record_a["workflow_projection_sha256"]
              == record_b["workflow_projection_sha256"]
              and record_a["frontier_record_sha256"]
              == record_b["frontier_record_sha256"])
        FINDINGS["comparisons"] = record_a["comparisons"]
        FINDINGS["pipeline_projection_sha256"] = record_a[
            "pipeline_projection_sha256"]
        FINDINGS["workflow_projection_sha256"] = record_a[
            "workflow_projection_sha256"]
        FINDINGS["frontier_record_sha256"] = record_a[
            "frontier_record_sha256"]

        banner("classifications")
        check("classify:image-identity",
              record_a["image_sha256"] == rederive_module.PRIVATE_IMAGE_SHA256
              and record_a["image_size"] == rederive_module.PRIVATE_SIZE
              and record_a["classification"]
              == "PRIVATE_LOCAL_COMPATIBILITY_FIXTURE")
        check("classify:ingestion-supported",
              record_a["ingestion_result"] == "SUPPORTED_MMC1"
              and record_a["mapper_platform_status"] == "SUPPORTED_MMC1"
              and record_a["mapper_variant_status"] == "SUPPORTED_PROFILE")
        check("classify:mapper-blocker-absent",
              record_a["comparisons"]["mapper_blocker_superseded"] is True)
        check("classify:power-on-state",
              record_a["power_on_registers"]
              == {"control": 12, "prg_bank": 0, "chr_bank_0": 0,
                  "chr_bank_1": 0}
              and record_a["power_on_prg_window"] == [0, 7]
              and record_a["prg_ram_enabled"] is False)

        candidate = record_a["reachable_static_frontier"]["candidate"]
        expected_candidate = rederive_module.EXPECTED_CANDIDATE
        check("classify:candidate-counts",
              all(candidate[key] == value
                  for key, value in expected_candidate.items()))
        check("classify:candidate-boundaries",
              candidate["low_window_range"] == [34330, 37267]
              and candidate["interrupt_sites"] == []
              and candidate["outside_targets"] == []
              and len(candidate["dynamic_returns"]) == 42)
        check("classify:opcode-histogram-forms",
              len(candidate["opcode_histogram"]) == 42)
        check("classify:opcode-stop",
              record_a["stop"] == rederive_module.EXPECTED_STOP
              and candidate["stop"] == rederive_module.EXPECTED_STOP)
        check("classify:opcode-frontier",
              record_a["opcode_frontier"]["status"]
              == "BLOCKED_UNSUPPORTED_OPCODE"
              and record_a["opcode_frontier"]["documented_forms"] == 42
              and record_a["opcode_frontier"]["unsupported"]
              == [{"address": 0xC570, "kind": "undocumented_opcode",
                   "reason": "0xc570: undocumented 6502 opcode 0x7c"}])
        check("classify:frontier-fail-closed",
              record_a["reachable_static_frontier"]["documented_status"]
              == "FAIL_CLOSED"
              and "0xc570" in record_a["reachable_static_frontier"]
              ["documented_error"])

        sites = record_a["indirect_control_flow_frontier"]["sites"]
        check("classify:indirect-unresolved",
              record_a["indirect_control_flow_frontier"]["status"]
              == "UNRESOLVED")
        check("classify:indirect-sites",
              [site["address"] for site in sites] == [0x86E8, 0x8956, 0x8F3C]
              and all(site["instruction"] == "jmp" and site["pointer"] == 0xE2
                      and site["classification"]
                      == "UNRESOLVED_INDIRECT_JUMP"
                      and site["targets"] == []
                      for site in sites))
        check("classify:indirect-in-candidate",
              candidate["indirect_sites"]
              == [{"address": 0x86E8, "instruction": "jmp", "pointer": 0xE2},
                  {"address": 0x8956, "instruction": "jmp", "pointer": 0xE2},
                  {"address": 0x8F3C, "instruction": "jmp", "pointer": 0xE2}])

        check("classify:blockers",
              tuple(item["classification"] for item in record_a["blockers"])
              == rederive_module.EXPECTED_BLOCKER_CLASSES
              and tuple(item["stage"] for item in record_a["blockers"])
              == rederive_module.EXPECTED_BLOCKER_STAGES)
        check("classify:progress",
              record_a["translation_progress"] == "NOT_ATTEMPTED"
              and record_a["generated_source_progress"] == "NOT_GENERATED"
              and record_a["native_build_progress"] == "NOT_ATTEMPTED"
              and record_a["native_execution_progress"] == "NOT_ATTEMPTED"
              and record_a["runtime_platform_progress"] == "NOT_TESTED")
        check("classify:runtime-support-identity",
              record_a["runtime_support_sha256"]
              == rederive_module.PRIVATE_SUPPORT_SHA256)
        check("classify:public-claim-none",
              record_a["public_claim"].startswith("none"))

        banner("negative")
        expect_rederive_fail(
            "missing-path",
            pathlib.Path(r"D:\OpenRecomp\Roms\phase1\nes\primary\absent.nes"))
        malformed = SCRATCH / "malformed_input.bin"
        malformed.write_bytes(b"OPENRECOMP-NOT-A-ROM\x00\x01\x02")
        expect_rederive_fail("malformed-container", malformed)

        banner("regressions")
        regressions = []
        for script in REGRESSIONS:
            record = run_regression(script)
            check(f"regression:{script}:exit", record["returncode"] == 0)
            check(f"regression:{script}:stderr", record["stderr_empty"])
            regressions.append(record)
        p7_00_regression = run_regression(
            P7_00_GATE, ["--evidence-dir",
                         ".openrecomp-phase7/scratch/P7-01/regression_p7_00"])
        check("regression:p7-00:exit", p7_00_regression["returncode"] == 0)
        check("regression:p7-00:stderr", p7_00_regression["stderr_empty"])
        check("regression:p7-00:marker",
              any(marker == "OPENRECOMP_P7_00=PASS"
                  for marker in p7_00_regression["markers"]))
        regressions.append(p7_00_regression)
        FINDINGS["regressions"] = regressions

        banner("evidence")
        write_json("frontier_rederivation.json", {
            "stage": STAGE,
            "classification": "PRIVATE_LOCAL_COMPATIBILITY_FIXTURE",
            "image_sha256": record_a["image_sha256"],
            "image_size": record_a["image_size"],
            "ingestion_result": record_a["ingestion_result"],
            "mapper_platform_status": record_a["mapper_platform_status"],
            "power_on_registers": record_a["power_on_registers"],
            "power_on_prg_window": record_a["power_on_prg_window"],
            "reachable_static_frontier":
                record_a["reachable_static_frontier"],
            "opcode_frontier": record_a["opcode_frontier"],
            "indirect_control_flow_frontier":
                record_a["indirect_control_flow_frontier"],
            "blockers": record_a["blockers"],
            "translation_progress": record_a["translation_progress"],
            "generated_source_progress":
                record_a["generated_source_progress"],
            "native_build_progress": record_a["native_build_progress"],
            "native_execution_progress":
                record_a["native_execution_progress"],
            "runtime_platform_progress":
                record_a["runtime_platform_progress"],
            "runtime_support_sha256": record_a["runtime_support_sha256"],
            "comparisons": record_a["comparisons"],
            "pipeline_projection_sha256":
                record_a["pipeline_projection_sha256"],
            "workflow_projection_sha256":
                record_a["workflow_projection_sha256"],
            "frontier_record_sha256": record_a["frontier_record_sha256"],
            "anchors": anchors,
            "public_claim": record_a["public_claim"],
        })
        private_bytes = private_fixture.PRIVATE_ROM.read_bytes()
        for name, data in EVIDENCE_WRITES.items():
            check(f"hygiene:no-private-rom-bytes:{name}",
                  private_bytes not in data)
        check("hygiene:no-rom-extension-in-scratch",
              not any(path.suffix.lower() in (".nes", ".fds", ".unf", ".unif")
                      for path in SCRATCH.rglob("*") if path.is_file()))
        workspace_files = [path.relative_to(workspace).as_posix()
                           for path in workspace.rglob("*") if path.is_file()] \
            if workspace.is_dir() else []
        check("hygiene:workspace-no-generated-rom-files", workspace_files == [])
        FINDINGS["workspace_files"] = workspace_files
    except Exception as exc:  # noqa: BLE001 - fail closed without traceback
        failure = f"{type(exc).__name__}: {exc}"

    passed = sum(1 for item in RESULTS if item["status"] == "PASS")
    failed = sum(1 for item in RESULTS if item["status"] == "FAIL") + (1 if failure else 0)
    status = "FAIL" if failure else "PASS"

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
            "compatibility": f"{COMPAT_MARKER}=NOT_PROVEN",
            "playability": f"{PLAYABILITY_MARKER}=NOT_PROVEN",
        },
        "checks": sorted(RESULTS, key=lambda item: item["check"]),
        "findings": FINDINGS,
        "failure": failure,
    }
    (EVIDENCE_DIR / "p7_01_tests.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        newline="\n")

    print("\n=== RESULT ===")
    print(f"{STAGE_MARKER}={status}")
    print(f"{FEATURE_MARKER}={status} tests={passed}")
    print(f"{TERMINAL_MARKER}=NOT_PROVEN")
    print(f"{COMPAT_MARKER}=NOT_PROVEN")
    print(f"{PLAYABILITY_MARKER}=NOT_PROVEN")
    if failure:
        print(f"FAILURE={failure}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
