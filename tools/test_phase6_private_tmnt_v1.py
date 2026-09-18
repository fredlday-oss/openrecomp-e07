#!/usr/bin/env python3
"""OpenRecomp Phase-6 private TMNT compatibility gate (P6-10).

Re-runs the audited pipeline stages against the private local compatibility
image (`PRIVATE_LOCAL_COMPATIBILITY_FIXTURE`) now that the MMC1 subset exists,
and verifies the exact deterministic result:

* ingestion classifies the image `SUPPORTED_MMC1` (8 x 16 KiB PRG, 16 x 8 KiB
  CHR, no PRG-RAM/battery/submapper) and extracts the power-on fixed-last-bank
  vectors;
* the P6-07 MMC1 cartridge service and the P6-09 independent reference platform
  both construct with the expected power-on mapper state;
* the frozen Phase-5 NROM mapper and bus still fail closed on mapper 1;
* the frozen documented-control-flow frontier fails closed at 0xC570
  (undocumented opcode 0x7C) and the bounded candidate traversal records the
  precise reachable counts, indirect jump sites and bank-window ambiguity;
* the shared neutral structure attempt fails closed for missing code/data span
  evidence; host translation and native execution are not attempted;
* MMC1 runtime support generation for the private image is deterministic and
  recorded by hash only.

No ROM bytes are stored in evidence; TMNT playability is not required.

On success it emits::

    OPENRECOMP_P6_10=PASS
    OPENRECOMP_PHASE6_PRIVATE_COMPAT_V1=PASS tests=<count>
    OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase6_private_tmnt_v1.py \
        --evidence-dir .openrecomp-phase6/evidence/P6-10
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
PHASE6 = ROOT / ".openrecomp-phase6"
for entry in (str(PHASE6 / "src"), str(ROOT / ".openrecomp-phase5" / "src"),
              str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import p6_private_run_v1 as private_run  # noqa: E402

STAGE = "P6-10"
STAGE_MARKER = "OPENRECOMP_P6_10"
FEATURE_MARKER = "OPENRECOMP_PHASE6_PRIVATE_COMPAT_V1"
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
PRG_BANKS = 8
CHR_BANKS = 16

FROZEN_FRONTIER_ERROR = ("reachable decode failed at 0xc570: 0xc570: "
                         "undocumented 6502 opcode 0x7c")
STRUCTURE_ERROR_PREFIX = ("P6FrontierError: proof fixture metadata declares "
                          "no data spans")
CANDIDATE = {
    "instructions": 1250,
    "bytes": 2711,
    "low_window_instructions": 1048,
    "fixed_window_instructions": 202,
    "distinct_opcode_forms": 42,
    "pending_at_stop": 11,
    "stop_address": 0xC570,
    "stop_kind": "undocumented_opcode",
    "stop_predecessor_address": 0xC56D,
    "stop_predecessor_instruction": "jsr",
}
INDIRECT_SITES = [
    {"address": 0x86E8, "instruction": "jmp", "pointer": 0x00E2},
    {"address": 0x8956, "instruction": "jmp", "pointer": 0x00E2},
    {"address": 0x8F3C, "instruction": "jmp", "pointer": 0x00E2},
]
SUPPORT_SHA256 = "2e3fa4bac6c0630840535aff2827c5f453b2372d0acb90551c72a58309d8a3e7"

REGRESSIONS = (
    ("tools/test_nes_rom_v1.py", []),
    ("tools/test_nes_platform_v1.py", []),
    ("tools/test_phase6_mmc1_inventory_v1.py",
     ["--evidence-dir", ".openrecomp-phase6/scratch/P6-10/regression_p6_01"]),
    ("tools/test_phase6_mmc1_variant_v1.py",
     ["--evidence-dir", ".openrecomp-phase6/scratch/P6-10/regression_p6_05"]),
    ("tools/test_phase6_mmc1_reference_equiv_v1.py",
     ["--evidence-dir", ".openrecomp-phase6/scratch/P6-10/regression_p6_09"]),
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


def expect_fail(label: str, thunk) -> None:
    try:
        thunk()
    except private_run.PrivateRunError:
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
    return {
        "script": script,
        "extra": extra,
        "returncode": completed.returncode,
        "stdout_bytes": len(completed.stdout),
        "stdout_sha256_raw": sha256_bytes(completed.stdout),
        "stdout_sha256_lf": sha256_bytes(lf_normalize(completed.stdout)),
        "stderr_bytes": len(completed.stderr),
        "stderr_empty": len(completed.stderr) == 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P6-10 private TMNT compatibility gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase6/evidence/P6-10")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}

    print("=== P6-10 Private TMNT Compatibility Gate ===", flush=True)
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
        check("control-plane:stage-row", "| P6-10 |" in queue)
        check("control-plane:terminal-reserved",
              f"{TERMINAL_MARKER}=NOT_PROVEN" in queue)
        check("control-plane:compat-reserved",
              f"{COMPAT_MARKER}=NOT_PROVEN" in queue
              and f"{COMPAT_MARKER}=NOT_PROVEN" in state)

        banner("analysis")
        report_a = private_run.run()
        report_b = private_run.run()
        check("analysis:deterministic", canonical(report_a) == canonical(report_b))
        check("private:path", report_a["source_path"] == PRIVATE_PATH)
        check("private:sha256",
              report_a["image_sha256"] == PRIVATE_SHA256
              and report_a["image_size"] == PRIVATE_SIZE)
        check("private:container-mapper",
              report_a["container"] == "nes2.0"
              and report_a["mapper"] == 1
              and report_a["submapper"] == 0
              and report_a["mirroring"] == "horizontal")
        check("private:prg-chr",
              report_a["prg_bytes"] == 0x20000
              and report_a["chr_bytes"] == 0x20000
              and report_a["chr_is_ram"] is False
              and report_a["battery"] is False
              and report_a["trainer_bytes"] == 0
              and report_a["four_screen"] is False)
        check("private:segment-hashes",
              report_a["prg_sha256"] == PRIVATE_PRG_SHA256
              and report_a["chr_sha256"] == PRIVATE_CHR_SHA256)
        check("private:vectors",
              report_a["vectors"] == VECTORS
              and report_a["vectors_source"] == "mmc1_power_on_fixed_last_bank")

        banner("mmc1_classification")
        classification = report_a["mmc1_classification"]
        check("mmc1:status",
              classification["status"] == "SUPPORTED_MMC1"
              and classification["reasons"] == []
              and classification["prg_banks_16k"] == PRG_BANKS
              and classification["chr_banks_8k"] == CHR_BANKS)
        check("mmc1:power-on",
              classification["power_on_control"] == 0x0C
              and classification["power_on_prg_mode"] == 3
              and classification["power_on_chr_mode"] == 0
              and classification["power_on_mirroring"] == "one_screen_lower")
        check("mmc1:variant-profile",
              report_a["variant_classification"]["status"] == "SUPPORTED_PROFILE"
              and report_a["variant_classification"]["profile"]
              == "discrete_mmc1_chr_rom_no_wram")
        check("mmc1:p6-01-delta",
              report_a["p6_01_recorded_execution_status"]
              == "BLOCKED_MMC1_MAPPER_NOT_YET_IMPLEMENTED"
              and report_a["ingestion"]["execution_status"]
              == "BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE")
        check("mmc1:superseded-blocker",
              any(item["code"] == "SUPERSEDED"
                  and "BLOCKED_MMC1_MAPPER_NOT_YET_IMPLEMENTED" in item["detail"]
                  for item in report_a["blockers"]))

        banner("cartridge_service")
        cartridge = report_a["cartridge"]
        check("cartridge:constructs",
              cartridge["status"] == "SUPPORTED_MMC1"
              and cartridge["prg_banks_16k"] == PRG_BANKS
              and cartridge["chr_banks_8k"] == CHR_BANKS)
        check("cartridge:power-on-state",
              cartridge["power_on_registers"] == {
                  "control": 0x0C, "chr_bank_0": 0, "chr_bank_1": 0, "prg_bank": 0}
              and cartridge["power_on_prg_window"] == [0, 7]
              and cartridge["power_on_chr_mode"] == 0
              and cartridge["power_on_mirroring"] == "one_screen_lower"
              and cartridge["prg_ram_enabled"] is False)

        banner("reference_platform")
        reference = report_a["reference_platform"]
        check("reference:power-on-state",
              reference["power_on_prg_window"] == [0, 7]
              and reference["power_on_registers"] == [0x0C, 0, 0, 0]
              and reference["power_on_chr_banks"]["bank_0"] == 0
              and reference["power_on_chr_banks"]["bank_1"] == 0)
        check("reference:reset-vector-readback",
              reference["reset_vector_readback"] == VECTORS["reset"])

        banner("phase5_boundary")
        preserved = report_a["preserved_phase5_boundary"]
        check("phase5:frozen-mapper-fail-closed",
              preserved["frozen_mapper_status"] == "FAIL_CLOSED"
              and "mapper 1" in preserved["frozen_mapper_error"])
        check("phase5:p5-bus-fail-closed",
              preserved["p5_bus_status"] == "FAIL_CLOSED"
              and "mapper 1" in preserved["p5_bus_error"])

        banner("frontier")
        frontier_report = report_a["frontier"]
        check("frontier:frozen-fail-closed",
              frontier_report["frozen_status"] == "FAIL_CLOSED"
              and frontier_report["frozen_error"] == FROZEN_FRONTIER_ERROR)
        candidate = frontier_report["candidate"]
        check("frontier:candidate-counts",
              candidate["instructions"] == CANDIDATE["instructions"]
              and candidate["bytes"] == CANDIDATE["bytes"]
              and candidate["low_window_instructions"]
              == CANDIDATE["low_window_instructions"]
              and candidate["fixed_window_instructions"]
              == CANDIDATE["fixed_window_instructions"]
              and candidate["distinct_opcode_forms"]
              == CANDIDATE["distinct_opcode_forms"]
              and candidate["pending_at_stop"] == CANDIDATE["pending_at_stop"]
              and candidate["truncated"] is False)
        stop = candidate["stop"] or {}
        check("frontier:candidate-stop",
              stop.get("address") == CANDIDATE["stop_address"]
              and stop.get("kind") == CANDIDATE["stop_kind"]
              and stop.get("predecessor", {}).get("address")
              == CANDIDATE["stop_predecessor_address"]
              and stop.get("predecessor", {}).get("instruction")
              == CANDIDATE["stop_predecessor_instruction"])
        check("frontier:indirect-sites",
              candidate["indirect_sites"] == INDIRECT_SITES)
        check("frontier:outside-targets",
              candidate["outside_targets"] == [])
        check("frontier:dynamic-returns",
              len(candidate["dynamic_returns"]) > 0
              and candidate["interrupt_sites"] == [])

        banner("structure_translation_runtime")
        check("structure:fail-closed",
              report_a["structure"]["status"] == "FAIL_CLOSED"
              and report_a["structure"]["error"] == STRUCTURE_ERROR_PREFIX)
        check("translation:not-attempted",
              report_a["translation"]["status"] == "NOT_ATTEMPTED")
        check("runtime:support-generated",
              report_a["runtime_support"]["status"] == "OK"
              and report_a["runtime_support"]["support_sha256"] == SUPPORT_SHA256
              and report_a["runtime_support"]["plan"] == [0x00, 0x01, 0x80])
        check("native:not-attempted",
              report_a["native_build"]["status"] == "NOT_ATTEMPTED"
              and report_a["native_execution"]["status"] == "NOT_ATTEMPTED")

        banner("blockers")
        blockers = report_a["blockers"]
        check("blockers:codes",
              [item["code"] for item in blockers] == [
                  "BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE",
                  "BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE",
                  "BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE",
                  "NOT_TESTED",
                  "SUPERSEDED"])
        check("blockers:frontier-detail",
              any("0xc570" in item["detail"] for item in blockers))
        check("blockers:indirect-detail",
              all(f"0x{item['address']:04x}" in blockers[1]["detail"]
                  for item in INDIRECT_SITES)
              and "0x00e2" in blockers[1]["detail"])
        check("blockers:bank-state-detail",
              "1048" in blockers[2]["detail"]
              and "$8000-$BFFF" in blockers[2]["detail"])
        check("blockers:public-none",
              report_a["public_claim"].startswith("none"))

        banner("negative")
        expect_fail("missing-private-path",
                    lambda: private_run.run(
                        path=pathlib.Path(
                            r"D:\OpenRecomp\Roms\phase1\nes\primary\absent.nes")))
        expect_fail("empty-plan", lambda: private_run.run(plan=()))
        expect_fail("plan-value-range", lambda: private_run.run(plan=(0x100,)))
        expect_fail("budget-range", lambda: private_run.run(budget=0))

        banner("regressions")
        regressions = []
        for script, extra in REGRESSIONS:
            record = run_regression(script, extra)
            check(f"regression:{script}:exit", record["returncode"] == 0)
            check(f"regression:{script}:stderr", record["stderr_empty"])
            regressions.append(record)
        FINDINGS["regressions"] = regressions

        banner("evidence_hygiene")
        write_json("tmnt_pipeline.json", report_a)
        write_json("blockers.json", {
            "stage": STAGE,
            "execution_status": "BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE",
            "blockers": blockers,
            "public_claim": report_a["public_claim"],
        })
        write_json("regressions.json", {"stage": STAGE, "regressions": regressions})
        rom = pathlib.Path(PRIVATE_PATH).read_bytes()
        last_bank = rom[-0x4000:]
        first_bank = rom[16:16 + 0x4000]
        for name, data in EVIDENCE_WRITES.items():
            check(f"hygiene:no-private-rom-bytes:{name}", rom not in data)
            check(f"hygiene:no-private-bank-bytes:{name}",
                  last_bank not in data and first_bank not in data)
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
    (EVIDENCE_DIR / "p6_10_tests.json").write_text(
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
