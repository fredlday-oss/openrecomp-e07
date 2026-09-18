#!/usr/bin/env python3
"""OpenRecomp Phase-5 private TMNT compatibility analysis gate (P5-11).

Verifies the private local compatibility fixture analysis: pinned hashes,
iNES metadata, fail-closed mapper/cartridge classification, the candidate
SxROM fixed-bank vector frame, the bounded candidate instruction frontier and
the precise blockers. The analysis is metadata/derived-only: no ROM bytes are
stored in evidence, and TMNT is not required to pass as a compatibility
target.

On success it emits::

    OPENRECOMP_P5_11=PASS
    OPENRECOMP_PHASE5_PRIVATE_COMPAT_V1=PASS tests=<count>
    OPENRECOMP_PHASE5_NES_PLATFORM_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE5_GENERAL_NES_COMPATIBILITY=NOT_PROVEN
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / ".openrecomp-phase5" / "src"), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import p5_private_tmnt_v1 as private  # noqa: E402

STAGE = "P5-11"
STAGE_MARKER = "OPENRECOMP_P5_11"
FEATURE_MARKER = "OPENRECOMP_PHASE5_PRIVATE_COMPAT_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE5_NES_PLATFORM_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE5_GENERAL_NES_COMPATIBILITY"

PRIVATE_PATH = r"D:\OpenRecomp\Roms\phase1\nes\primary\tmnt.nes"
PRIVATE_SHA256 = "2a9345e608ec0c57470dc6658ce8199ddea9c18076134d9ef2a56f91b0a066d1"
PRIVATE_SIZE = 262160
PRIVATE_PRG_SHA256 = "2fbc367a453504f01d7dec9fcc52c59b249fd8633ee8e5de6c7ec04abe0131bc"
PRIVATE_CHR_SHA256 = "f9e354d57423f5d883663ed56801066ce38ab1a64065a735db88d42aee6eac29"
CANDIDATE_VECTORS = {"nmi": 0xC3A3, "reset": 0xFFD8, "irq": 0xC412}
FRONTIER_INSTRUCTIONS = 351
FRONTIER_FORMS = 59
OUTSIDE_TARGETS = [0x864C, 0x901E]
STOP_REASON_PREFIX = "decode: 0xc570"

REGRESSIONS = (
    ("tools/test_nes_rom_v1.py", []),
    ("tools/test_phase5_ingestion_v1.py",
     ["--evidence-dir", ".openrecomp-phase5/scratch/regression_p5_11_p5_01"]),
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


def lf_normalize(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def canonical(document: Any) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_json(name: str, document: Any) -> None:
    EVIDENCE_WRITES[name] = canonical(document)


def run_regression(script: str, extra: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(ROOT / script), *extra],
        cwd=str(ROOT), capture_output=True)
    return {
        "script": script,
        "returncode": completed.returncode,
        "stdout_bytes": len(completed.stdout),
        "stdout_sha256_raw": sha256_bytes(completed.stdout),
        "stdout_sha256_lf": sha256_bytes(lf_normalize(completed.stdout)),
        "stderr_bytes": len(completed.stderr),
        "stderr_empty": len(completed.stderr) == 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="P5-11 private compatibility gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase5/evidence/P5-11")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}

    print("=== P5-11 Private TMNT Compatibility Gate ===", flush=True)
    failure: str | None = None
    try:
        banner("analysis")
        report_a = private.analyse()
        report_b = private.analyse()
        check("analysis:deterministic", canonical(report_a) == canonical(report_b))
        check("private:path", report_a["source_path"] == PRIVATE_PATH)
        check("private:sha256", report_a["image_sha256"] == PRIVATE_SHA256)
        check("private:size", report_a["image_size"] == PRIVATE_SIZE)
        check("private:container", report_a["container"] == "nes2.0")
        check("private:mapper", report_a["mapper"] == 1)
        check("private:mirroring", report_a["mirroring"] == "horizontal")
        check("private:prg-chr",
              report_a["prg_bytes"] == 0x20000
              and report_a["chr_bytes"] == 0x20000
              and report_a["chr_is_ram"] is False)
        check("private:hashes",
              report_a["prg_sha256"] == PRIVATE_PRG_SHA256
              and report_a["chr_sha256"] == PRIVATE_CHR_SHA256)
        check("private:classification",
              report_a["classification"] == "PRIVATE_LOCAL_COMPATIBILITY_FIXTURE")
        check("private:blocked",
              report_a["execution_status"] == "BLOCKED_UNSUPPORTED_MAPPER")

        banner("fail_closed")
        check("fail-closed:mapper", report_a["mapper_fail_closed"] is True
              and "mapper 1" in report_a["mapper_error"])
        check("fail-closed:p5-cartridge",
              report_a["p5_cartridge_fail_closed"] is True)

        banner("candidate_frame")
        frame = report_a["candidate_frame"]
        check("candidate:claim", frame["claim"] == "CANDIDATE / NOT PROVEN")
        check("candidate:vectors", frame["vectors"] == CANDIDATE_VECTORS)
        check("candidate:basis",
              "power-on fixed-bank frame" in frame["basis"]
              and "unresolved" in frame["basis"])

        banner("candidate_frontier")
        frontier = report_a["candidate_frontier"]
        check("frontier:claim", frontier["claim"] == "CANDIDATE / NOT PROVEN")
        check("frontier:instructions",
              frontier["instructions"] == FRONTIER_INSTRUCTIONS)
        check("frontier:forms", frontier["distinct_opcode_forms"] == FRONTIER_FORMS)
        check("frontier:outside-targets",
              frontier["outside_bank_targets"] == OUTSIDE_TARGETS)
        check("frontier:stopped", frontier["truncated"] is False
              and frontier["stop_reason"].startswith(STOP_REASON_PREFIX))

        banner("blockers")
        codes = [item["code"] for item in report_a["blockers"]]
        check("blockers:codes",
              "BLOCKED_UNSUPPORTED_MAPPER" in codes
              and "BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE" in codes)
        check("blockers:banking",
              any("MMC1" in item["detail"] for item in report_a["blockers"]))
        check("blockers:out-of-bank",
              any("0x864c" in item["detail"].lower()
                  for item in report_a["blockers"]))
        check("blockers:public-none",
              report_a["public_claim"].startswith("none"))

        banner("regressions")
        regressions = []
        for script, extra in REGRESSIONS:
            record = run_regression(script, extra)
            check(f"regression:{script}:exit", record["returncode"] == 0)
            check(f"regression:{script}:stderr", record["stderr_empty"])
            regressions.append(record)
        FINDINGS["regressions"] = regressions

        banner("evidence")
        write_json("tmnt_analysis.json", report_a)
        write_json("blockers.json", {
            "stage": STAGE,
            "blockers": report_a["blockers"],
            "execution_status": report_a["execution_status"],
            "public_claim": report_a["public_claim"],
        })
        write_json("regressions.json", {"stage": STAGE, "regressions": regressions})

        rom = pathlib.Path(PRIVATE_PATH).read_bytes()
        check("hygiene:no-private-rom-in-evidence",
              all(rom not in data for data in EVIDENCE_WRITES.values()))
        check("hygiene:no-private-bank-in-evidence",
              all(rom[-0x4000:] not in data for data in EVIDENCE_WRITES.values()))
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
    (EVIDENCE_DIR / "p5_11_tests.json").write_text(
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
