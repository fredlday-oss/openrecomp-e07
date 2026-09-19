#!/usr/bin/env python3
"""OpenRecomp Phase-7 reusable bank-aware ROM-to-native workflow gate (P7-14).

Runs the workflow on the public bank-switching fixture, the public
indirect-flow fixture and the private compatibility image; verifies
deterministic reports, generated native sources/builds where supported,
explicit fail-closed blockers otherwise and workspace hygiene (no copied
source ROM, no ROM-extension files).

On success it emits::

    OPENRECOMP_P7_14=PASS
    OPENRECOMP_PHASE7_BANK_WORKFLOW_V1=PASS tests=<count>
    OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN
    OPENRECOMP_PHASE7_TMMT_PLAYABILITY=NOT_PROVEN

Usage:

    python tools/test_phase7_workflow_v1.py \
        --evidence-dir .openrecomp-phase7/evidence/P7-14
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
CONTROL7 = ROOT / ".openrecomp-phase7"
for entry in (str(ROOT), str(ROOT / "tools"),
              str(ROOT / ".openrecomp-phase5" / "src"),
              str(ROOT / ".openrecomp-phase6" / "src"),
              str(CONTROL7 / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import adapters.nes6502 as nes  # noqa: E402
import p6_private_fixture_v1 as private_fixture  # noqa: E402
import p7_bank_switching_fixture_v1 as bank_fixture  # noqa: E402
import p7_indirect_flow_fixture_v1 as indirect_fixture  # noqa: E402
import p7_workflow_v1 as workflow  # noqa: E402

STAGE = "P7-14"
STAGE_MARKER = "OPENRECOMP_P7_14"
FEATURE_MARKER = "OPENRECOMP_PHASE7_BANK_WORKFLOW_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE7_TMMT_PLAYABILITY"

P7_13_RECORD_REL = ".openrecomp-phase7/evidence/P7-13/p7_13_tests.json"
P7_13_GATE = "tools/test_phase7_private_run2_v1.py"
PRIVATE_SHA256 = (
    "2a9345e608ec0c57470dc6658ce8199ddea9c18076134d9ef2a56f91b0a066d1")

ROM_EXTENSIONS = (".nes", ".fds", ".unf", ".unif", ".prg", ".chr")

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


def canonical_text(document: Any) -> str:
    return json.dumps(document, sort_keys=True, separators=(",", ":"))


def write_json(name: str, document: Any) -> None:
    EVIDENCE_WRITES[name] = canonical(document)


def read_json(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def run_regression(script: str, extra: list[str] | None = None) -> dict[str, Any]:
    completed = subprocess.run([sys.executable, script, *(extra or [])],
                               cwd=str(ROOT), capture_output=True)
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


def write_fixture_rom(rom: bytes, path: pathlib.Path) -> pathlib.Path:
    path.write_bytes(rom)
    return path


def scan_workspace(workspace: pathlib.Path, size: int,
                   digest: str) -> tuple[list[str], list[str]]:
    copies = []
    extensions = []
    for item in workspace.rglob("*"):
        if not item.is_file():
            continue
        if item.suffix.lower() in ROM_EXTENSIONS:
            extensions.append(item.name)
        if item.stat().st_size == size and sha256_file(item) == digest:
            copies.append(item.name)
    return copies, extensions


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P7-14 bank-aware ROM-to-native workflow gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase7/evidence/P7-14")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES, SCRATCH
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    SCRATCH = CONTROL7 / "scratch" / "P7-14"
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}

    print("=== P7-14 Bank-Aware ROM-to-Native Workflow Gate ===", flush=True)
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
        check("anchor:p7-13-record-pass",
              read_json(ROOT / P7_13_RECORD_REL)["status"] == "PASS")
        check("anchor:decoder-unchanged", len(nes.OPCODES) == 151)

        banner("control_plane")
        state = (CONTROL7 / "STATE.md").read_text(encoding="utf-8")
        queue = (CONTROL7 / "STAGE_QUEUE.md").read_text(encoding="utf-8")
        check("control-plane:stage-row", "| P7-14 |" in queue)
        check("control-plane:terminal-reserved",
              f"{TERMINAL_MARKER}=NOT_PROVEN" in queue
              and f"{TERMINAL_MARKER}=NOT_PROVEN" in state)
        check("control-plane:compat-reserved",
              f"{COMPAT_MARKER}=NOT_PROVEN" in queue
              and f"{COMPAT_MARKER}=NOT_PROVEN" in state)
        check("control-plane:playability-reserved",
              f"{PLAYABILITY_MARKER}=NOT_PROVEN" in queue
              and f"{PLAYABILITY_MARKER}=NOT_PROVEN" in state)

        banner("public_bank_switching")
        bank_rom, bank_metadata = bank_fixture.build()
        bank_path = write_fixture_rom(bank_rom, SCRATCH / "bank_switching.rom-local")
        bank_workspace = SCRATCH / "bank_workspace"
        bank_workspace_b = SCRATCH / "bank_workspace_b"
        bank_report = workflow.run(bank_path, workspace=bank_workspace)
        bank_repeat = workflow.run(bank_path, workspace=bank_workspace_b)
        check("bank:deterministic",
              canonical_text(bank_report) == canonical_text(bank_repeat))
        check("bank:status", bank_report["status"] == "COMPLETED")
        check("bank:inventory",
              bank_report["inventory"]["status"] == "OK"
              and bank_report["inventory"]["mapper"] == 1
              and bank_report["inventory"]["prg_banks_16k"] == 4)
        check("bank:frontier",
              bank_report["bank_frontier"]["status"] == "OK"
              and bank_report["bank_frontier"]["proven_instructions"]
              == bank_metadata["instructions_cross_checked"]
              and bank_report["bank_frontier"]["unresolved_instructions"] == 0)
        check("bank:translation",
              bank_report["translation"]["status"] == "TRANSLATED"
              and bank_report["generated_sources"]["status"] == "GENERATED")
        check("bank:native-build",
              bank_report["native_build"]["status"] == "BUILT"
              and bank_report["native_build"]["classification"]
              == "EXECUTABLE_REPRODUCIBLE"
              and bank_report["native_build"]["executable_reproducible"]
              is True)
        copies, extensions = scan_workspace(bank_workspace,
                                            bank_metadata["rom_size"],
                                            bank_metadata["rom_sha256"])
        check("bank:no-rom-copy", copies == [] and extensions == [])
        FINDINGS["bank_switching"] = {
            key: bank_report[key] for key in
            ("status", "bank_frontier", "indirect_control_flow",
             "inline_closure", "generated_sources", "native_build", "blockers")}

        banner("public_indirect_flow")
        indirect_rom, indirect_metadata = indirect_fixture.build()
        indirect_path = write_fixture_rom(
            indirect_rom, SCRATCH / "indirect_flow.rom-local")
        indirect_workspace = SCRATCH / "indirect_workspace"
        indirect_report = workflow.run(indirect_path,
                                       workspace=indirect_workspace)
        indirect_repeat = workflow.run(
            indirect_path, workspace=SCRATCH / "indirect_workspace_b")
        check("indirect:deterministic",
              canonical_text(indirect_report) == canonical_text(indirect_repeat))
        check("indirect:status",
              indirect_report["status"] == "COMPLETED_WITH_FRONTIER")
        check("indirect:classification",
              indirect_report["indirect_control_flow"]["counts"]
              == {"RESOLVED_EXACT": 1, "RESOLVED_FINITE_SET": 1,
                  "UNRESOLVED": 1})
        site_states = {entry["site"]: entry["classification"]
                       for entry in indirect_report["indirect_control_flow"]
                       ["sites"]}
        check("indirect:sites",
              site_states == {0x8013: "RESOLVED_EXACT",
                              0x8025: "RESOLVED_FINITE_SET",
                              0x8030: "UNRESOLVED"})
        check("indirect:assignment-policy",
              indirect_report["specialization"]["assignment_policy"]
              == "lowest_target"
              and len(indirect_report["specialization"]["dispatch"]) == 2
              and len(indirect_report["specialization"]["frontier"]) == 1)
        check("indirect:generated-and-built",
              indirect_report["generated_sources"]["status"] == "GENERATED"
              and indirect_report["native_build"]["status"] == "BUILT"
              and indirect_report["native_build"]["executable_reproducible"]
              is True)
        check("indirect:blocker-recorded",
              any(item["code"] == "UNRESOLVED_INDIRECT_SITE"
                  for item in indirect_report["blockers"]))
        copies, extensions = scan_workspace(
            indirect_workspace, indirect_metadata["rom_size"],
            indirect_metadata["rom_sha256"])
        check("indirect:no-rom-copy", copies == [] and extensions == [])
        FINDINGS["indirect_flow"] = {
            key: indirect_report[key] for key in
            ("status", "bank_frontier", "indirect_control_flow",
             "generated_sources", "native_build", "blockers")}

        banner("private_image")
        private_path = private_fixture.PRIVATE_ROM
        private_workspace = SCRATCH / "private_workspace"
        private_report = workflow.run(private_path, workspace=private_workspace)
        check("private:fail-closed",
              private_report["status"] == "FAIL_CLOSED"
              and private_report["generated_sources"]["status"]
              == "NOT_GENERATED"
              and private_report["native_build"]["status"] == "NOT_ATTEMPTED")
        codes = {item["code"] for item in private_report["blockers"]}
        check("private:blockers",
              "BANK_FRONTIER_INCOMPLETE" in codes
              and "UNSUPPORTED_INDIRECT_POINTER" in codes)
        check("private:identity-only",
              private_report["input"]["image_sha256"] == PRIVATE_SHA256
              and private_report["input"]["source_rom_copied"] is False
              and private_fixture.PRIVATE_ROM.read_bytes()
              not in canonical_text(private_report).encode("utf-8"))
        copies, extensions = scan_workspace(private_workspace, 262160,
                                            PRIVATE_SHA256)
        check("private:no-rom-copy", copies == [] and extensions == [])
        FINDINGS["private"] = {
            "status": private_report["status"],
            "blockers": private_report["blockers"],
        }

        banner("regressions")
        regressions = [run_regression("tools/test_nes_rom_v1.py")]
        check("regression:nes-rom-tool:exit",
              regressions[0]["returncode"] == 0)
        check("regression:nes-rom-tool:stderr",
              regressions[0]["stderr_empty"])
        p7_13_regression = run_regression(
            P7_13_GATE, ["--evidence-dir",
                         ".openrecomp-phase7/scratch/P7-14/regression_p7_13"])
        check("regression:p7-13:exit", p7_13_regression["returncode"] == 0)
        check("regression:p7-13:stderr", p7_13_regression["stderr_empty"])
        check("regression:p7-13:marker",
              any(marker == "OPENRECOMP_P7_13=PASS"
                  for marker in p7_13_regression["markers"]))
        regressions.append(p7_13_regression)
        FINDINGS["regressions"] = regressions

        banner("evidence")
        write_json("workflow.json", {
            "stage": STAGE,
            "workflow": workflow.WORKFLOW_ID,
            "bank_switching": FINDINGS["bank_switching"],
            "indirect_flow": FINDINGS["indirect_flow"],
            "private_image": FINDINGS["private"],
            "hygiene": {
                "source_rom_copied": False,
                "no_rom_extension_files": True,
                "no_byte_identical_copy": True,
            },
            "public_claim": "bounded reusable workflow only; no general "
                            "compatibility claim",
        })
        private_bytes = private_fixture.PRIVATE_ROM.read_bytes()
        for name, data in EVIDENCE_WRITES.items():
            check(f"hygiene:no-private-rom-bytes:{name}", private_bytes not in data)
        check("hygiene:no-rom-extension-in-scratch",
              not any(item.suffix.lower() in ROM_EXTENSIONS
                      for item in SCRATCH.rglob("*") if item.is_file()))
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
    for name, data in EVIDENCE_WRITES.items():
        (EVIDENCE_DIR / name).write_bytes(data)
    (EVIDENCE_DIR / "p7_14_tests.json").write_text(
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
