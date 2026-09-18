#!/usr/bin/env python3
"""OpenRecomp Phase-6 second private TMNT compatibility gate (P6-13).

Runs the complete local pipeline through the frozen P6-12 reusable workflow
(`p6_workflow_v1`) against the existing private local compatibility image
(`PRIVATE_LOCAL_COMPATIBILITY_FIXTURE`) and records, metadata/hash only:

* ingestion result and mapper/platform state;
* the reachable/static frontier (documented walk result and bounded candidate
  traversal counts);
* the opcode frontier (undocumented opcode stop);
* the indirect-control-flow frontier (`jmp ($E2)` sites);
* translation, generated-source, native-build and runtime/platform progress;
* the exact stop reason(s);
* whether native execution is reached (no) and whether meaningful interactive
  behaviour is reached (no).

The recorded frontier is anchored byte-for-byte to the committed P6-10
compatibility evidence and the committed P6-12 workflow classification; the
in-memory MMC1 runtime support identity is re-derived without writing any
ROM-derived source. TMNT playability is not required for Phase-6 PASS, and no
ROM bytes are copied, stored, echoed or packaged.

On success it emits::

    OPENRECOMP_P6_13=PASS
    OPENRECOMP_PHASE6_PRIVATE_COMPAT_RUN2_V1=PASS tests=<count>
    OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase6_private_workflow_v1.py \
        --evidence-dir .openrecomp-phase6/evidence/P6-13
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
PHASE6 = ROOT / ".openrecomp-phase6"
for entry in (str(PHASE6 / "src"), str(ROOT / ".openrecomp-phase5" / "src"),
              str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import p6_emit_v1 as emit_module  # noqa: E402
import p6_ines_v1 as ingestion  # noqa: E402
import p6_private_fixture_v1 as private_fixture  # noqa: E402
import p6_workflow_v1 as workflow  # noqa: E402

STAGE = "P6-13"
STAGE_MARKER = "OPENRECOMP_P6_13"
FEATURE_MARKER = "OPENRECOMP_PHASE6_PRIVATE_COMPAT_RUN2_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY"

PHASE5_TAG_OBJECT = "b5d6832ba2374b810f4c24500ed9093a9481fd8d"
PHASE5_COMMIT = "e8d3627a622d0ca3196b117c5112f29fabdb49e7"
PHASE5_TREE = "468fb9788350de393d3de2ca9471b7d874ee8dc9"

PRIVATE_PATH = r"D:\OpenRecomp\Roms\phase1\nes\primary\tmnt.nes"
PRIVATE_SHA256 = "2a9345e608ec0c57470dc6658ce8199ddea9c18076134d9ef2a56f91b0a066d1"
PRIVATE_SIZE = 262160
PRIVATE_PRG_SHA256 = "2fbc367a453504f01d7dec9fcc52c59b249fd8633ee8e5de6c7ec04abe0131bc"
PRIVATE_CHR_SHA256 = "f9e354d57423f5d883663ed56801066ce38ab1a64065a735db88d42aee6eac29"
VECTORS = {"nmi": 0xC3A3, "reset": 0xFFD8, "irq": 0xC412}

P6_10_PIPELINE_REL = ".openrecomp-phase6/evidence/P6-10/tmnt_pipeline.json"
P6_10_PIPELINE_SHA256 = (
    "0b8c9014fa11f9e363f1cfb1c569048f786b8baec2117769adb862b375a3ebdc")
P6_10_BLOCKERS_REL = ".openrecomp-phase6/evidence/P6-10/blockers.json"
P6_10_BLOCKERS_SHA256 = (
    "6b8b789cb691da742c270b81c98849bbda952642ad393cc5a4af230bc97e41c5")
P6_12_BLOCKERS_REL = ".openrecomp-phase6/evidence/P6-12/blockers.json"
P6_12_BLOCKERS_SHA256 = (
    "b5cb9ef40625195baef160717ae15647091d6b6b0a13c2f24b9c8dab5c4ea579")
PRIVATE_SUPPORT_SHA256 = (
    "2e3fa4bac6c0630840535aff2827c5f453b2372d0acb90551c72a58309d8a3e7")

CANDIDATE = {
    "instructions": 1250,
    "bytes": 2711,
    "low_window_instructions": 1048,
    "fixed_window_instructions": 202,
    "distinct_opcode_forms": 42,
    "pending_at_stop": 11,
}
STOP = {
    "address": 0xC570,
    "kind": "undocumented_opcode",
    "reason": "0xc570: undocumented 6502 opcode 0x7c",
    "predecessor_address": 0xC56D,
    "predecessor_instruction": "jsr",
}
INDIRECT = [
    {"address": 0x86E8, "instruction": "jmp", "pointer": 0x00E2,
     "classification": "UNRESOLVED_INDIRECT_JUMP", "targets": []},
    {"address": 0x8956, "instruction": "jmp", "pointer": 0x00E2,
     "classification": "UNRESOLVED_INDIRECT_JUMP", "targets": []},
    {"address": 0x8F3C, "instruction": "jmp", "pointer": 0x00E2,
     "classification": "UNRESOLVED_INDIRECT_JUMP", "targets": []},
]
BLOCKER_CLASSES = ["unsupported_opcode", "unresolved_indirect_control_flow",
                   "bank_state_unresolved", "platform_runtime_not_tested"]
STOP_REASON = ("BLOCKED_UNSUPPORTED_OPCODE (opcode_frontier): "
               "documented-control-flow walk fails closed at 0xc570 "
               "(0xc570: undocumented 6502 opcode 0x7c) after 1250 candidate "
               "instructions; no code/data boundary evidence is declared")

REGRESSIONS = (
    ("tools/test_nes_rom_v1.py", []),
    ("tools/test_nes_platform_v1.py", []),
    ("tools/test_phase6_mmc1_inventory_v1.py",
     ["--evidence-dir", ".openrecomp-phase6/scratch/P6-13/regression_p6_01"]),
    ("tools/test_phase6_mmc1_variant_v1.py",
     ["--evidence-dir", ".openrecomp-phase6/scratch/P6-13/regression_p6_05"]),
    ("tools/test_phase6_mmc1_reference_equiv_v1.py",
     ["--evidence-dir", ".openrecomp-phase6/scratch/P6-13/regression_p6_09"]),
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


def lf_normalize(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def canonical(document: Any) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True)
            + "\n").encode("utf-8")


def write_json(name: str, document: Any) -> None:
    EVIDENCE_WRITES[name] = canonical(document)


def verify_anchor(path: pathlib.Path, expected: str) -> str:
    if not path.is_file():
        raise AssertionError(f"evidence anchor is missing: {path.name}")
    actual = sha256_file(path)
    if actual != expected:
        raise AssertionError(
            f"evidence anchor changed: {path.name} is {actual}, expected "
            f"{expected}")
    return actual


def expect_workflow_fail(label: str, thunk) -> None:
    try:
        thunk()
    except workflow.P6WorkflowError:
        check(f"reject:{label}", True)
        return
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(
            f"reject:{label}: raised {type(exc).__name__}: {exc}") from exc
    raise AssertionError(f"reject:{label}: accepted")


def run_regression(script: str, extra: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(ROOT / script), *extra], cwd=str(ROOT),
        capture_output=True)
    markers = [line for line in
               completed.stdout.decode("utf-8", errors="replace").splitlines()
               if line.startswith("OPENRECOMP_")]
    return {
        "script": script,
        "extra": extra,
        "returncode": completed.returncode,
        "stdout_bytes": len(completed.stdout),
        "stdout_sha256_raw": sha256_bytes(completed.stdout),
        "stdout_sha256_lf": sha256_bytes(lf_normalize(completed.stdout)),
        "stderr_bytes": len(completed.stderr),
        "stderr_empty": len(completed.stderr) == 0,
        "markers": markers,
    }


def workspace_inventory(workspace: pathlib.Path) -> list[str]:
    if not workspace.is_dir():
        return []
    return sorted(path.relative_to(workspace).as_posix()
                  for path in workspace.rglob("*") if path.is_file())


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P6-13 second private TMNT compatibility gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase6/evidence/P6-13")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}
    scratch = ROOT / ".openrecomp-phase6" / "scratch" / "P6-13"
    workspace_dir = scratch / "workspace"
    if workspace_dir.exists():
        shutil.rmtree(workspace_dir)

    print("=== P6-13 Second Private TMNT Compatibility Gate ===", flush=True)
    failure: str | None = None
    try:
        banner("source_integrity")
        manifest = PHASE6 / "SOURCE_SHA256SUMS.txt"
        check("source:manifest-exists", manifest.is_file())
        entries = []
        for line in manifest.read_text(encoding="utf-8").strip().splitlines():
            digest, rel = line.split(" *", 1)
            entries.append((digest, rel))
        bad = [rel for digest, rel in entries
               if not (ROOT / rel).is_file() or sha256_file(ROOT / rel) != digest]
        check("source:manifest-verified", bool(entries) and not bad)

        banner("frozen_chain")
        check("chain:phase5-tag-object",
              subprocess.run(["git", "rev-parse", "openrecomp-phase5-pass"],
                             cwd=str(ROOT), capture_output=True, text=True
                             ).stdout.strip() == PHASE5_TAG_OBJECT)
        check("chain:phase5-commit",
              subprocess.run(["git", "rev-parse", "openrecomp-phase5-pass^{commit}"],
                             cwd=str(ROOT), capture_output=True, text=True
                             ).stdout.strip() == PHASE5_COMMIT)
        check("chain:phase5-tree",
              subprocess.run(["git", "rev-parse", "openrecomp-phase5-pass^{tree}"],
                             cwd=str(ROOT), capture_output=True, text=True
                             ).stdout.strip() == PHASE5_TREE)
        check("chain:descends",
              subprocess.run(["git", "merge-base", "--is-ancestor", PHASE5_COMMIT,
                              "HEAD"], cwd=str(ROOT), capture_output=True
              ).returncode == 0)

        banner("control_plane")
        state = (PHASE6 / "STATE.md").read_text(encoding="utf-8")
        queue = (PHASE6 / "STAGE_QUEUE.md").read_text(encoding="utf-8")
        check("control-plane:stage-row", "| P6-13 |" in queue)
        check("control-plane:terminal-reserved",
              f"{TERMINAL_MARKER}=NOT_PROVEN" in queue)
        check("control-plane:compat-reserved",
              f"{COMPAT_MARKER}=NOT_PROVEN" in queue
              and f"{COMPAT_MARKER}=NOT_PROVEN" in state)

        banner("anchors")
        pipeline_path = ROOT / P6_10_PIPELINE_REL
        verify_anchor(pipeline_path, P6_10_PIPELINE_SHA256)
        check("anchor:p6-10-pipeline-hash", True)
        p6_10 = json.loads(pipeline_path.read_text(encoding="utf-8"))
        blockers_path = ROOT / P6_10_BLOCKERS_REL
        verify_anchor(blockers_path, P6_10_BLOCKERS_SHA256)
        check("anchor:p6-10-blockers-hash", True)
        p6_12_blockers_path = ROOT / P6_12_BLOCKERS_REL
        verify_anchor(p6_12_blockers_path, P6_12_BLOCKERS_SHA256)
        check("anchor:p6-12-blockers-hash", True)
        p6_12_blockers = json.loads(
            p6_12_blockers_path.read_text(encoding="utf-8"))

        banner("private_workflow")
        report_a = workflow.run(private_fixture.PRIVATE_ROM, build=True,
                                workspace=workspace_dir)
        report_b = workflow.run(private_fixture.PRIVATE_ROM, build=True,
                                workspace=workspace_dir)
        check("workflow:deterministic",
              canonical(report_a) == canonical(report_b))
        check("workflow:status",
              report_a["status"] == "FAIL_CLOSED"
              and report_a["stop_reason"] == STOP_REASON)
        check("workflow:input-identity",
              report_a["input"]["source_path"] == PRIVATE_PATH
              and report_a["input"]["source_classification"]
              == "PRIVATE_LOCAL_COMPATIBILITY_FIXTURE"
              and report_a["input"]["image_sha256"] == PRIVATE_SHA256
              and report_a["input"]["image_size"] == PRIVATE_SIZE
              and report_a["input"]["source_rom_copied"] is False)

        banner("ingestion_result")
        inventory = report_a["inventory"]
        check("ingestion:status", inventory["status"] == "OK"
              and inventory["container"] == "nes2.0"
              and inventory["mapper"] == 1
              and inventory["submapper"] == 0
              and inventory["mirroring"] == "horizontal")
        check("ingestion:segments",
              inventory["prg_bytes"] == 0x20000
              and inventory["chr_bytes"] == 0x20000
              and inventory["chr_is_ram"] is False
              and inventory["battery"] is False
              and inventory["trainer_bytes"] == 0
              and inventory["four_screen"] is False
              and inventory["prg_sha256"] == PRIVATE_PRG_SHA256
              and inventory["chr_sha256"] == PRIVATE_CHR_SHA256)
        check("ingestion:vectors",
              inventory["vectors"] == VECTORS
              and inventory["vectors_source"]
              == "mmc1_power_on_fixed_last_bank")

        banner("mapper_state")
        platform = report_a["mapper_platform"]
        check("mapper:status",
              platform["status"] == "SUPPORTED_MMC1"
              and platform["classification"]["prg_banks_16k"] == 8
              and platform["classification"]["chr_banks_8k"] == 16)
        check("mapper:variant",
              platform["variant"]["status"] == "SUPPORTED_PROFILE"
              and platform["variant"]["profile"]
              == "discrete_mmc1_chr_rom_no_wram")
        check("mapper:power-on",
              platform["cartridge"]["power_on_registers"]
              == {"control": 0x0C, "chr_bank_0": 0, "chr_bank_1": 0,
                  "prg_bank": 0}
              and platform["cartridge"]["power_on_prg_window"] == [0, 7]
              and platform["cartridge"]["power_on_chr_mode"] == 0
              and platform["cartridge"]["power_on_mirroring"]
              == "one_screen_lower"
              and platform["cartridge"]["prg_ram_enabled"] is False)

        banner("reachable_frontier")
        frontier = report_a["frontier"]
        check("frontier:documented-fail-closed",
              frontier["documented_status"] == "FAIL_CLOSED"
              and "0xc570" in frontier["documented_error"])
        candidate = frontier["candidate"]
        check("frontier:candidate-counts",
              all(candidate[key] == value
                  for key, value in CANDIDATE.items())
              and candidate["truncated"] is False
              and candidate["low_window_range"] is not None)
        stop = candidate["stop"] or {}
        check("frontier:stop",
              stop.get("address") == STOP["address"]
              and stop.get("kind") == STOP["kind"]
              and stop.get("reason") == STOP["reason"]
              and stop.get("predecessor", {}).get("address")
              == STOP["predecessor_address"]
              and stop.get("predecessor", {}).get("instruction")
              == STOP["predecessor_instruction"])
        check("frontier:no-code-region",
              frontier["code_region"] is None
              and frontier["contiguous"] is False)

        banner("opcode_frontier")
        opcode = report_a["opcode_frontier"]
        check("opcode:blocked",
              opcode["status"] == "BLOCKED_UNSUPPORTED_OPCODE"
              and opcode["documented_forms"] == CANDIDATE["distinct_opcode_forms"]
              and opcode["unsupported"] == [{
                  "address": STOP["address"],
                  "kind": STOP["kind"],
                  "reason": STOP["reason"]}])

        banner("indirect_control_flow_frontier")
        check("indirect:unresolved",
              report_a["indirect_control_flow"]["status"] == "UNRESOLVED"
              and report_a["indirect_control_flow"]["sites"] == INDIRECT)

        banner("progress")
        check("progress:translation-not-attempted",
              report_a["translation"]["status"] == "NOT_ATTEMPTED")
        check("progress:generated-not-generated",
              report_a["generated_sources"]["status"] == "NOT_GENERATED"
              and report_a["generated_sources"].get("written", []) == [])
        check("progress:native-build-not-attempted",
              report_a["native_build"]["status"] == "NOT_ATTEMPTED")
        check("progress:native-execution-not-attempted",
              report_a["native_execution"]["status"] == "NOT_ATTEMPTED")
        check("progress:platform-not-tested",
              report_a["platform_runtime"]["status"] == "NOT_TESTED")
        check("progress:blockers-exact",
              [item["classification"] for item in report_a["blockers"]]
              == BLOCKER_CLASSES
              and [item["stage"] for item in report_a["blockers"]]
              == ["opcode_frontier", "indirect_control_flow", "bank_state",
                  "runtime_platform"])
        check("progress:native-execution-not-reached",
              report_a["native_execution"]["status"] != "EXECUTED")
        check("progress:interactive-not-reached",
              report_a["generated_sources"]["status"] != "GENERATED"
              and report_a["platform_runtime"]["status"] !=
              "BOUNDED_NES_PLATFORM_MODEL_ACTIVE")
        check("progress:public-claim-none",
              report_a["public_claim"].startswith("none"))

        banner("runtime_support")
        metadata = {
            "rom_sha256": report_a["input"]["image_sha256"],
            "prg_size": inventory["prg_bytes"],
            "chr_size": inventory["chr_bytes"],
            "prg_banks": platform["classification"]["prg_banks_16k"],
            "chr_banks": platform["classification"]["chr_banks_8k"],
        }
        private_bytes = private_fixture.PRIVATE_ROM.read_bytes()
        support = emit_module.emit_support(private_bytes, metadata,
                                           workflow.DEFAULT_PLAN)
        support_hash = sha256_bytes(support.encode("utf-8"))
        del support
        check("runtime:support-identity",
              support_hash == PRIVATE_SUPPORT_SHA256)
        check("runtime:support-not-written",
              workspace_inventory(workspace_dir) == [])
        check("runtime:support-matches-p6-10",
              p6_10["runtime_support"]["support_sha256"] == support_hash
              and p6_10["runtime_support"]["status"] == "OK")

        banner("p6_10_anchor_cross_check")
        frozen_candidate = p6_10["frontier"]["candidate"]
        check("cross-check:candidate",
              all(frozen_candidate[key] == value
                  for key, value in CANDIDATE.items())
              and frozen_candidate["stop"]["address"] == STOP["address"]
              and frozen_candidate["indirect_sites"]
              == [{"address": item["address"], "instruction": item["instruction"],
                   "pointer": item["pointer"]} for item in INDIRECT])
        check("cross-check:pipeline-status",
              p6_10["translation"]["status"] == "NOT_ATTEMPTED"
              and p6_10["native_build"]["status"] == "NOT_ATTEMPTED"
              and p6_10["native_execution"]["status"] == "NOT_ATTEMPTED")
        check("cross-check:p6-12-blockers",
              p6_12_blockers["private_image"] == report_a["blockers"]
              and p6_12_blockers["private_stop_reason"]
              == report_a["stop_reason"])
        check("cross-check:same-blockers-remain",
              [item["classification"] for item in
               p6_12_blockers["private_image"]] == BLOCKER_CLASSES
              and p6_10["blockers"][0]["code"]
              == "BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE"
              and "0xc570" in p6_10["blockers"][0]["detail"]
              and "0x86e8" in p6_10["blockers"][1]["detail"]
              and "1048" in p6_10["blockers"][2]["detail"])

        banner("negative")
        expect_workflow_fail(
            "missing-private-path",
            lambda: workflow.run(pathlib.Path(
                r"D:\OpenRecomp\Roms\phase1\nes\primary\absent.nes")))
        expect_workflow_fail(
            "empty-plan",
            lambda: workflow.run(private_fixture.PRIVATE_ROM, plan=()))
        expect_workflow_fail(
            "budget-range",
            lambda: workflow.run(private_fixture.PRIVATE_ROM, budget=0))

        banner("regressions")
        regressions = []
        for script, extra in REGRESSIONS:
            record = run_regression(script, extra)
            check(f"regression:{script}:exit", record["returncode"] == 0)
            check(f"regression:{script}:stderr", record["stderr_empty"])
            regressions.append(record)
        check("regression:p6-09-reference-equivalence-marker",
              any("OPENRECOMP_PHASE6_MMC1_REFERENCE_EQUIVALENCE_V1=PASS"
                  in marker for marker in regressions[-1]["markers"]))
        FINDINGS["regressions"] = regressions

        banner("evidence_hygiene")
        write_json("private_workflow.json", {
            "stage": STAGE,
            "classification": "PRIVATE_LOCAL_COMPATIBILITY_FIXTURE",
            "report": report_a,
            "native_execution_reached": False,
            "interactive_behaviour_reached": False,
            "runtime_support_sha256": support_hash,
            "public_claim": report_a["public_claim"],
        })
        write_json("frontier_record.json", {
            "stage": STAGE,
            "ingestion_result": "SUPPORTED_MMC1",
            "mapper_state": {
                "status": platform["status"],
                "variant": platform["variant"]["status"],
                "power_on_prg_window": platform["cartridge"]
                ["power_on_prg_window"],
                "power_on_registers": platform["cartridge"]
                ["power_on_registers"],
            },
            "reachable_static_frontier": {
                "documented_status": frontier["documented_status"],
                "documented_error": frontier["documented_error"],
                "candidate": candidate,
            },
            "opcode_frontier": opcode,
            "indirect_control_flow_frontier":
                report_a["indirect_control_flow"],
            "translation_progress": report_a["translation"]["status"],
            "generated_source_progress":
                report_a["generated_sources"]["status"],
            "native_build_progress": report_a["native_build"]["status"],
            "native_execution_progress":
                report_a["native_execution"]["status"],
            "runtime_platform_progress":
                report_a["platform_runtime"]["status"],
            "stop_reasons": report_a["blockers"],
            "stop_reason": report_a["stop_reason"],
            "native_execution_reached": False,
            "interactive_behaviour_reached": False,
        })
        write_json("anchors.json", {
            "stage": STAGE,
            "p6_10_pipeline_sha256": P6_10_PIPELINE_SHA256,
            "p6_10_blockers_sha256": P6_10_BLOCKERS_SHA256,
            "p6_12_blockers_sha256": P6_12_BLOCKERS_SHA256,
            "private_support_sha256": PRIVATE_SUPPORT_SHA256,
            "private_image_sha256": PRIVATE_SHA256,
        })
        write_json("regressions.json", {"stage": STAGE, "regressions": regressions})
        last_bank = private_bytes[-0x4000:]
        first_bank = private_bytes[16:16 + 0x4000]
        for name, data in EVIDENCE_WRITES.items():
            check(f"hygiene:no-private-rom-bytes:{name}", private_bytes not in data)
            check(f"hygiene:no-private-bank-bytes:{name}",
                  last_bank not in data and first_bank not in data)
        check("hygiene:workspace-empty", workspace_inventory(workspace_dir) == [])
        FINDINGS["evidence_files"] = sorted(EVIDENCE_WRITES)
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
        },
        "checks": sorted(RESULTS, key=lambda item: item["check"]),
        "findings": FINDINGS,
        "failure": failure,
    }
    for name, data in EVIDENCE_WRITES.items():
        (EVIDENCE_DIR / name).write_bytes(data)
    (EVIDENCE_DIR / "p6_13_tests.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        newline="\n")

    print("\n=== RESULT ===")
    print(f"{STAGE_MARKER}={status}")
    print(f"{FEATURE_MARKER}={status} tests={passed}")
    print(f"{TERMINAL_MARKER}=NOT_PROVEN")
    print(f"{COMPAT_MARKER}=NOT_PROVEN")
    if failure:
        print(f"FAILURE={failure}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
