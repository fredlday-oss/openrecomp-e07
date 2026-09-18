#!/usr/bin/env python3
"""OpenRecomp Phase-5 2A03/6502 decode + reachable frontier gate (P5-02).

Verifies the exact reachable/dead/unsupported instruction frontier of the
original public fixture from its reset/NMI/IRQ roots, the explicit indirect /
interrupt / dynamic-return sites, the 2A03 decimal-mode accounting, and that
the frozen NES6502 frontend converts the real fixture code region into IR V1
fail-closed.

On success it emits::

    OPENRECOMP_P5_02=PASS
    OPENRECOMP_PHASE5_DECODE_FRONTIER_V1=PASS tests=<count>
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
for entry in (str(ROOT / ".openrecomp-phase5" / "src"), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import nes6502_frontend_v1 as frozen_frontend  # noqa: E402
import p5_fixture_build_v1 as fixture_build  # noqa: E402
import p5_frontier_v1 as frontier  # noqa: E402
import p5_ines_v1 as ingestion  # noqa: E402

STAGE = "P5-02"
STAGE_MARKER = "OPENRECOMP_P5_02"
FEATURE_MARKER = "OPENRECOMP_PHASE5_DECODE_FRONTIER_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE5_NES_PLATFORM_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE5_GENERAL_NES_COMPATIBILITY"

PUBLIC_ROM_SHA256 = "272c94cdc79463cd1020ff14db1892ba56af07e4cfda97f5f1df89dd807772b9"
REACHABLE_INSTRUCTIONS = 230
REACHABLE_BYTES = 508
OPCODE_HISTOGRAM_SHA256 = "f2609143e2fc6606127c8d72f19efb9c23ff92f032154dd42a5003cc7551a28c"
MODE_HISTOGRAM_SHA256 = "cf91f914381a37a7d9ce2462854d5deb6049ac44f950d980a654740637c2a398"
REACHABLE_SECTION_SHA256 = "3dbcb989b820f70ce2c3092518f99c8890909b84a4c4efef509f2bfaf8e8864f"
CPU_IMAGE_SHA256 = "eda59866f8add232b1064d1d9952a3d3e66ad9b7c1fe06604dff0e610f5bcecb"
INDIRECT_SITES = [{"address": 49405, "instruction": "jmp", "indirect": 767}]
INTERRUPT_SITES = [{"address": 49318, "instruction": "brk", "continuation": 49320}]
DYNAMIC_RETURN_COUNT = 9
DEAD_ADDRESSES = [49319]
LINEAR_INSTRUCTIONS = 231
FRONTEND_BLOCKS = 45

REGRESSIONS = (
    ("tools/test_nes6502_decode_v1.py", []),
    ("tools/test_nes6502_lowering_v1.py", []),
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


def expect_fail(label: str, thunk, error_types) -> None:
    try:
        thunk()
    except error_types:
        check(f"reject:{label}", True)
        return
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(
            f"reject:{label}: raised {type(exc).__name__}: {exc}") from exc
    raise AssertionError(f"reject:{label}: accepted")


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
    parser = argparse.ArgumentParser(description="P5-02 decode/frontier gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase5/evidence/P5-02")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}

    print("=== P5-02 2A03/6502 Decode + Reachable Frontier Gate ===", flush=True)
    failure: str | None = None
    try:
        banner("fixture_and_image")
        rom, metadata = fixture_build.build()
        inventory = ingestion.ingest(rom, source_label="public_fixture")
        document = inventory.to_document()
        check("fixture:rom-sha256", metadata["rom_sha256"] == PUBLIC_ROM_SHA256)
        check("fixture:status", document["execution_status"] == "SUPPORTED_NROM")
        image = frontier.build_cpu_image(rom, 16, metadata["prg_size"])
        check("image:64k", len(image) == 0x10000)
        check("image:sha256", sha256_bytes(image) == CPU_IMAGE_SHA256)

        banner("reachable_frontier")
        analysis_a = frontier.analysis(rom, metadata, document)
        analysis_b = frontier.analysis(rom, metadata, document)
        check("frontier:deterministic", canonical(analysis_a) == canonical(analysis_b))
        reachable = analysis_a["reachable"]
        check("frontier:roots", analysis_a["roots"]
              == {"reset": 0xC000, "nmi": 0xC196, "irq": 0xC1F7})
        check("frontier:instructions",
              reachable["instructions"] == REACHABLE_INSTRUCTIONS)
        check("frontier:bytes", reachable["bytes"] == REACHABLE_BYTES)
        check("frontier:opcode-histogram", sha256_bytes(canonical(
            reachable["opcode_histogram"])) == OPCODE_HISTOGRAM_SHA256)
        check("frontier:mode-histogram", sha256_bytes(canonical(
            reachable["mode_histogram"])) == MODE_HISTOGRAM_SHA256)
        check("frontier:reachable-section", sha256_bytes(canonical(
            reachable)) == REACHABLE_SECTION_SHA256)
        check("frontier:indirect-sites", reachable["indirect_sites"] == INDIRECT_SITES)
        check("frontier:interrupt-sites",
              reachable["interrupt_sites"] == INTERRUPT_SITES)
        check("frontier:dynamic-returns",
              len(reachable["dynamic_return_sites"]) == DYNAMIC_RETURN_COUNT)
        span = analysis_a["code_span"]
        check("frontier:code-span",
              span["span"] == [0xC000, 0xC1FD]
              and span["linear_instructions"] == LINEAR_INSTRUCTIONS
              and span["reachable_in_span"] == REACHABLE_INSTRUCTIONS
              and span["dead_in_span"] == len(DEAD_ADDRESSES)
              and span["dead_addresses"] == DEAD_ADDRESSES)
        check("frontier:unsupported-zero",
              analysis_a["unsupported"]["reachable_undocumented_opcodes"] == 0)
        check("frontier:decimal-mode",
              analysis_a["decimal_mode"]["arithmetic"] == "binary_only_2a03"
              and "sed" in analysis_a["decimal_mode"]["instructions_present"])

        banner("negative")
        illegal = bytearray(image)
        illegal[0xC000] = 0x02  # undocumented JAM opcode at the reset root
        expect_fail("reachable-undocumented-opcode",
                    lambda: frontier.reachable_frontier(bytes(illegal), [0xC000]),
                    (frontier.FrontierError,))
        expect_fail("nrom-prg-size",
                    lambda: frontier.build_cpu_image(b"\x00" * 0x4000, 16, 0x1000),
                    (frontier.FrontierError,))
        bad_region = dict(metadata)
        bad_region["data_spans"] = []
        expect_fail("missing-data-spans",
                    lambda: frontier.code_region_from_metadata(bad_region),
                    (frontier.FrontierError,))

        banner("frozen_frontend")
        region_start, region_end = frontier.code_region_from_metadata(metadata)
        contract = json.loads(
            (ROOT / "contracts" / "host_contract.json").read_text(encoding="utf-8"))
        frontend_meta = {
            "architecture": "nes6502",
            "entry_address": region_start,
            "region_start": region_start,
            "region_end": region_end,
            "initial_state": {
                "cpu:a": 0x00, "cpu:x": 0x00, "cpu:y": 0x00, "cpu:sp": 0xFD,
                "cpu:pc": region_start, "cpu:p": 0x24, "platform:halted": 0,
            },
            "observe_state_slot": "cpu:a",
            "max_operations": 1000000,
        }
        ir_a, sidecar_a, report_a = frozen_frontend.convert(image, frontend_meta, contract)
        ir_b, sidecar_b, report_b = frozen_frontend.convert(image, frontend_meta, contract)
        check("frontend:deterministic", canonical(ir_a) == canonical(ir_b)
              and canonical(report_a) == canonical(report_b))
        check("frontend:instructions", report_a["instructions"] == LINEAR_INSTRUCTIONS)
        check("frontend:blocks", report_a["blocks"] == FRONTEND_BLOCKS)
        check("frontend:region", report_a["source_region"] == [region_start, region_end])
        check("frontend:input-sha", report_a["source_input_sha256"] == CPU_IMAGE_SHA256)
        illegal_image = bytearray(image)
        illegal_image[0xC000] = 0x03  # undocumented SLO (izx); 0x02 is the
        # frozen frontend's synthetic halt sentinel and is not used here
        expect_fail("frontend-undocumented-opcode",
                    lambda: frozen_frontend.convert(bytes(illegal_image),
                                                    frontend_meta, contract),
                    (frozen_frontend.NES6502FrontendError,))

        banner("regressions")
        regressions = []
        for script, extra in REGRESSIONS:
            record = run_regression(script, extra)
            check(f"regression:{script}:exit", record["returncode"] == 0)
            check(f"regression:{script}:stderr", record["stderr_empty"])
            regressions.append(record)
        FINDINGS["regressions"] = regressions

        banner("evidence")
        write_json("frontier.json", analysis_a)
        write_json("frontend.json", {
            "stage": STAGE,
            "frontend": ".openrecomp-phase5/src/p5_frontier_v1.py + "
                        "tools/nes6502_frontend_v1.py",
            "meta": frontend_meta,
            "report": report_a,
            "ir_sha256": sha256_bytes(canonical(ir_a)),
            "sidecar_sha256": sha256_bytes(canonical(sidecar_a)),
        })
        write_json("regressions.json", {"stage": STAGE, "regressions": regressions})
        for name, data in EVIDENCE_WRITES.items():
            check(f"hygiene:no-public-rom-bytes:{name}", rom not in data)
        FINDINGS["evidence_files"] = sorted(EVIDENCE_WRITES)
        FINDINGS["reachable_instructions"] = reachable["instructions"]
        FINDINGS["indirect_sites"] = reachable["indirect_sites"]
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
    (EVIDENCE_DIR / "p5_02_tests.json").write_text(
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
