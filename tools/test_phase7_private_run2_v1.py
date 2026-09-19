#!/usr/bin/env python3
"""OpenRecomp Phase-7 second private TMNT frontier gate (P7-13).

Re-runs the complete private pipeline with the P7-12 closure applied and
records the exact new frontier: the inline table is closed, the frontier
advances to the next undocumented byte, bank provenance remains partially
unresolved, translation/native execution are not reached and platform
behaviour is still untestable. Metadata/derived evidence only.

On success it emits::

    OPENRECOMP_P7_13=PASS
    OPENRECOMP_PHASE7_PRIVATE_FRONTIER_RUN2_V1=PASS tests=<count>
    OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN
    OPENRECOMP_PHASE7_TMMT_PLAYABILITY=NOT_PROVEN

Usage:

    python tools/test_phase7_private_run2_v1.py \
        --evidence-dir .openrecomp-phase7/evidence/P7-13
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
import p7_inline_closure_v1 as closure  # noqa: E402
import p7_opcode_7c_v1 as opcode_module  # noqa: E402
import p7_private_frontier_v1 as private_frontier  # noqa: E402

STAGE = "P7-13"
STAGE_MARKER = "OPENRECOMP_P7_13"
FEATURE_MARKER = "OPENRECOMP_PHASE7_PRIVATE_FRONTIER_RUN2_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE7_TMMT_PLAYABILITY"

P7_12_RECORD_REL = ".openrecomp-phase7/evidence/P7-12/p7_12_tests.json"
P7_12_GATE = "tools/test_phase7_translation_closure_v1.py"
PRIVATE_SHA256 = (
    "2a9345e608ec0c57470dc6658ce8199ddea9c18076134d9ef2a56f91b0a066d1")

REGRESSIONS = ("tools/test_nes_rom_v1.py",)

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


def build_record() -> dict[str, Any]:
    data = private_fixture.PRIVATE_ROM.read_bytes()
    image, inventory = opcode_module.build_image(data)
    roots = [inventory["vectors"][name] for name in ("reset", "nmi", "irq")]
    frontier = private_frontier.run()
    closed = closure.analyze(image, roots)
    stop = closed["closure"]["stop"]
    blockers = [
        {"classification": "undocumented_opcode_unclassified",
         "code": "BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE",
         "stage": "opcode_frontier",
         "detail": f"closure walk advances past 0xC570 and stops at "
                   f"0x{stop['address']:04x} ({stop['reason']}); the byte is "
                   "not yet classified"},
        {"classification": "bank_state_unresolved",
         "code": "BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE",
         "stage": "bank_state",
         "detail": f"{frontier['p7_bank_frontier']['unresolved_instructions']}"
                   " unresolved candidate identities across banks remain "
                   "(bounded expansion)"},
        {"classification": "platform_runtime_not_tested",
         "code": "NOT_TESTED",
         "stage": "runtime_platform",
         "detail": "platform behaviour remains untestable until a complete "
                   "proven translation exists"},
    ]
    return {
        "stage": "P7-13",
        "classification": "PRIVATE_LOCAL_COMPATIBILITY_FIXTURE",
        "image_sha256": inventory["image_sha256"],
        "image_size": inventory["actual_size"],
        "closure": {
            "tables": closed["tables"],
            "instructions": closed["closure"]["instructions"],
            "baseline_instructions": closed["baseline"]["instructions"],
            "delta_instructions": closed["delta_instructions"],
            "stop": stop,
        },
        "p7_bank_frontier": frontier["p7_bank_frontier"],
        "indirect_evidence_counts": frontier["indirect_evidence"]["counts"],
        "translation_progress": "NOT_ATTEMPTED",
        "native_build_progress": "NOT_ATTEMPTED",
        "native_execution_progress": "NOT_ATTEMPTED",
        "native_execution_reached": False,
        "interactive_behaviour_reached": False,
        "stop_reasons": blockers,
        "public_claim": "none; private local analysis must not enter the "
                        "public package",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P7-13 second private TMNT frontier gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase7/evidence/P7-13")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES, SCRATCH
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    SCRATCH = CONTROL7 / "scratch" / "P7-13"
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}

    print("=== P7-13 Second Private TMNT Frontier Gate ===", flush=True)
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
        check("anchor:p7-12-record-pass",
              read_json(ROOT / P7_12_RECORD_REL)["status"] == "PASS")
        check("anchor:decoder-unchanged", len(nes.OPCODES) == 151)
        check("anchor:private-image",
              private_fixture.PRIVATE_ROM.is_file()
              and sha256_file(private_fixture.PRIVATE_ROM) == PRIVATE_SHA256)

        banner("control_plane")
        state = (CONTROL7 / "STATE.md").read_text(encoding="utf-8")
        queue = (CONTROL7 / "STAGE_QUEUE.md").read_text(encoding="utf-8")
        check("control-plane:stage-row", "| P7-13 |" in queue)
        check("control-plane:terminal-reserved",
              f"{TERMINAL_MARKER}=NOT_PROVEN" in queue
              and f"{TERMINAL_MARKER}=NOT_PROVEN" in state)
        check("control-plane:compat-reserved",
              f"{COMPAT_MARKER}=NOT_PROVEN" in queue
              and f"{COMPAT_MARKER}=NOT_PROVEN" in state)
        check("control-plane:playability-reserved",
              f"{PLAYABILITY_MARKER}=NOT_PROVEN" in queue
              and f"{PLAYABILITY_MARKER}=NOT_PROVEN" in state)

        banner("second_private_run")
        record = build_record()
        record_repeat = build_record()
        check("private:deterministic",
              canonical_text(record) == canonical_text(record_repeat))
        check("private:closure-progress",
              record["closure"]["baseline_instructions"] == 1250
              and record["closure"]["instructions"] == 1255
              and record["closure"]["delta_instructions"] == 5
              and len(record["closure"]["tables"]) == 1
              and record["closure"]["tables"][0]["table_base"] == 0xC570
              and record["closure"]["tables"][0]["resume_address"] == 0xC57C)
        check("private:new-frontier",
              record["closure"]["stop"]["address"] == 0xBB6B
              and record["closure"]["stop"]["kind"] == "undocumented_opcode"
              and "0xe3" in record["closure"]["stop"]["reason"])
        check("private:bank-frontier",
              record["p7_bank_frontier"]["proven_instructions"] == 530
              and record["p7_bank_frontier"]["unresolved_instructions"]
              == 14027
              and record["p7_bank_frontier"]["unresolved_limited"] is True)
        check("private:progress-status",
              record["translation_progress"] == "NOT_ATTEMPTED"
              and record["native_build_progress"] == "NOT_ATTEMPTED"
              and record["native_execution_progress"] == "NOT_ATTEMPTED"
              and record["native_execution_reached"] is False
              and record["interactive_behaviour_reached"] is False)
        check("private:stop-reasons",
              [item["classification"] for item in record["stop_reasons"]]
              == ["undocumented_opcode_unclassified", "bank_state_unresolved",
                  "platform_runtime_not_tested"]
              and record["stop_reasons"][2]["code"] == "NOT_TESTED")
        check("private:no-rom-bytes",
              private_fixture.PRIVATE_ROM.read_bytes()
              not in canonical_text(record).encode("utf-8"))
        FINDINGS["closure"] = record["closure"]
        FINDINGS["stop_reasons"] = record["stop_reasons"]

        banner("regressions")
        regressions = []
        for script in REGRESSIONS:
            regression_record = run_regression(script)
            check(f"regression:{script}:exit",
                  regression_record["returncode"] == 0)
            check(f"regression:{script}:stderr",
                  regression_record["stderr_empty"])
            regressions.append(regression_record)
        p7_12_regression = run_regression(
            P7_12_GATE, ["--evidence-dir",
                         ".openrecomp-phase7/scratch/P7-13/regression_p7_12"])
        check("regression:p7-12:exit", p7_12_regression["returncode"] == 0)
        check("regression:p7-12:stderr", p7_12_regression["stderr_empty"])
        check("regression:p7-12:marker",
              any(marker == "OPENRECOMP_P7_12=PASS"
                  for marker in p7_12_regression["markers"]))
        regressions.append(p7_12_regression)
        FINDINGS["regressions"] = regressions

        banner("evidence")
        write_json("private_frontier_run2.json", record)
        private_bytes = private_fixture.PRIVATE_ROM.read_bytes()
        for name, data in EVIDENCE_WRITES.items():
            check(f"hygiene:no-private-rom-bytes:{name}", private_bytes not in data)
        check("hygiene:no-rom-extension-in-scratch",
              not any(path.suffix.lower() in (".nes", ".fds", ".unf", ".unif")
                      for path in SCRATCH.rglob("*") if path.is_file()))
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
    (EVIDENCE_DIR / "p7_13_tests.json").write_text(
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
