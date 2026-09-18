#!/usr/bin/env python3
"""OpenRecomp Phase-5 CPU semantics proof gate (P5-03).

Runs the complete differential vector suite (every documented NMOS 6502
official opcode plus flag/stack/branch/page-crossing/indirect-wrap/BRK-RTI/
2A03-decimal edge cases) through the frozen translation path and the frozen
independent reference interpreter, requiring exact final-state and full-memory
agreement, and verifies the documented reset/IRQ/NMI entry behaviour.

On success it emits::

    OPENRECOMP_P5_03=PASS
    OPENRECOMP_PHASE5_CPU_SEMANTICS_V1=PASS tests=<count>
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

import adapters.nes6502 as nes_adapter  # noqa: E402
import p5_fixture_build_v1 as fixture_build  # noqa: E402
import p5_ines_v1 as ingestion  # noqa: E402
import p5_semantics_v1 as semantics  # noqa: E402
from p5_fixture_asm_v1 import AssemblyError  # noqa: E402

STAGE = "P5-03"
STAGE_MARKER = "OPENRECOMP_P5_03"
FEATURE_MARKER = "OPENRECOMP_PHASE5_CPU_SEMANTICS_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE5_NES_PLATFORM_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE5_GENERAL_NES_COMPATIBILITY"

EXPECTED_VECTORS = 181
EXPECTED_PAIRS = 151
EXPECTED_FAILED = 0

EDGE_VECTORS = (
    "edge_adc_imm_7f_01",
    "edge_adc_imm_ff_01",
    "edge_adc_imm_80_80",
    "edge_adc_imm_00_ff_c",
    "edge_adc_abs_50_50_c",
    "edge_sbc_imm_00_01_c",
    "edge_sbc_imm_80_01_c",
    "edge_sbc_imm_50_f0_c",
    "edge_sbc_imm_00_00",
    "edge_bit_abs_40",
    "edge_inc_abs_7f",
    "edge_dec_abs_00",
    "edge_lda_zpx_wrap",
    "edge_lda_absx_page_cross",
    "edge_lda_absy_page_cross",
    "edge_lda_indy_page_cross",
    "edge_rmw_inc_absx_page_cross",
    "edge_cmp_imm_equal",
    "edge_cmp_imm_less",
    "edge_cpx_imm_greater",
    "edge_cpy_imm_equal",
    "edge_2a03_sed_adc_binary",
    "edge_2a03_sed_sbc_binary",
    "op_6c_jmp_ind",
    "op_00_brk_impl",
    "op_40_rti_impl",
    "op_20_jsr_abs",
)

REGRESSIONS = (
    ("tools/test_nes6502_semantics_v1.py", []),
    ("tools/test_nes6502_state_v1.py", []),
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


def canonical(document: Any) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


def lf_normalize(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


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
    parser = argparse.ArgumentParser(description="P5-03 CPU semantics gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase5/evidence/P5-03")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}

    print("=== P5-03 CPU Semantics Proof Gate ===", flush=True)
    failure: str | None = None
    try:
        banner("differential_suite")
        suite = semantics.run_suite()
        suite_hash = sha256_bytes(canonical(suite))
        check("suite:vector-count", suite["vectors"] == EXPECTED_VECTORS)
        check("suite:no-failed", len(suite["failed"]) == EXPECTED_FAILED
              and not suite["failed"])
        covered = {tuple(item) for item in suite["covered_pairs"]}
        official = {(mnemonic, mode)
                    for _opcode, (mnemonic, mode, _kind)
                    in sorted(nes_adapter.OPCODES.items())}
        check("suite:covered-pairs", len(covered) == EXPECTED_PAIRS)
        check("suite:official-coverage", covered == official)
        for name in EDGE_VECTORS:
            match = [item for item in suite["results"] if item["name"] == name]
            check(f"edge:{name}:present-and-passing",
                  len(match) == 1 and match[0]["equivalent"])
        FINDINGS["suite_sha256"] = suite_hash
        FINDINGS["vectors"] = suite["vectors"]

        banner("reachable_coverage")
        rom, metadata = fixture_build.build()
        inventory = ingestion.ingest(rom, source_label="public_fixture").to_document()
        reachable = set(semantics.reachable_pairs(
            rom, metadata, inventory))
        check("reachable:subset-of-covered", reachable <= covered)
        FINDINGS["reachable_pairs"] = sorted(list(item) for item in reachable)
        FINDINGS["reachable_count"] = len(reachable)

        banner("interrupts")
        interrupts = semantics.interrupt_document()
        for name in ("reset", "irq", "nmi"):
            check(f"interrupt:{name}", interrupts[name] == interrupts[f"{name}_expected"])
        FINDINGS["interrupt"] = interrupts

        banner("negative")
        expect_fail("undocumented-opcode", lambda: semantics.run_vector(
            semantics.Vector(
                name="negative-undocumented-opcode",
                source="\n".join([".org $0100", ".byte $03", ".byte $02"]) + "\n",
                covers=(("lda", "imm"),),
            )), (semantics.SemanticsError,))
        expect_fail("missing-terminator", lambda: semantics.run_vector(
            semantics.Vector(
                name="negative-missing-terminator",
                source="\n".join([".org $0100", "lda #$00"]) + "\n",
                covers=(("lda", "imm"),),
            )), (semantics.SemanticsError,))
        expect_fail("assembly-error", lambda: semantics.run_vector(
            semantics.Vector(
                name="negative-assembly-error",
                source="\n".join([".org $0100", "xyz #$00"]) + "\n",
                covers=(("lda", "imm"),),
            )), (semantics.SemanticsError,))

        banner("regressions")
        regressions = []
        for script, extra in REGRESSIONS:
            record = run_regression(script, extra)
            check(f"regression:{script}:exit", record["returncode"] == 0)
            check(f"regression:{script}:stderr", record["stderr_empty"])
            regressions.append(record)
        FINDINGS["regressions"] = regressions

        banner("evidence")
        write_json("semantics.json", suite)
        write_json("coverage.json", {
            "stage": STAGE,
            "official_pairs": [list(item) for item in sorted(official)],
            "covered_pairs": [list(item) for item in sorted(covered)],
            "reachable_pairs": FINDINGS["reachable_pairs"],
            "vectors": suite["vectors"],
            "failed": suite["failed"],
        })
        write_json("interrupt.json", interrupts)
        write_json("regressions.json", {"stage": STAGE, "regressions": regressions})
        for name, data in EVIDENCE_WRITES.items():
            check(f"hygiene:no-public-rom-bytes:{name}", rom not in data)
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
    (EVIDENCE_DIR / "p5_03_tests.json").write_text(
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
