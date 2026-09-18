#!/usr/bin/env python3
"""OpenRecomp Phase-6 MMC1 PRG banking gate (P6-03).

Differentially verifies the `MMC1_SUBSET_V1` PRG mapping implementation against
an independently structured reference over exhaustively bounded register/bank
combinations, verifies fixed-first/fixed-last and 32 KiB behaviour explicitly,
and verifies fail-closed behaviour for unsupported bank counts and addresses.

On success it emits::

    OPENRECOMP_P6_03=PASS
    OPENRECOMP_PHASE6_MMC1_PRG_V1=PASS tests=<count>
    OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase6_mmc1_prg_v1.py --evidence-dir .openrecomp-phase6/evidence/P6-03
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

import p6_fixture_build_v1 as fixture_build  # noqa: E402
import p6_mapper1_prg_reference_v1 as prg_reference  # noqa: E402
import p6_mapper1_prg_v1 as prg_model  # noqa: E402
import p6_mmc1_serial_v1 as serial_model  # noqa: E402
import p6_private_fixture_v1 as private_fixture  # noqa: E402

STAGE = "P6-03"
STAGE_MARKER = "OPENRECOMP_P6_03"
FEATURE_MARKER = "OPENRECOMP_PHASE6_MMC1_PRG_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY"

PHASE5_TAG_OBJECT = "b5d6832ba2374b810f4c24500ed9093a9481fd8d"
PHASE5_COMMIT = "e8d3627a622d0ca3196b117c5112f29fabdb49e7"
PHASE5_TREE = "468fb9788350de393d3de2ca9471b7d874ee8dc9"

PROBE_ADDRESSES = (0x8000, 0x9FFF, 0xA000, 0xBFFF, 0xC000, 0xDFFF, 0xE000,
                   0xFFFF)

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


def write_json(name: str, document: dict[str, Any]) -> None:
    data = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")
    EVIDENCE_WRITES[name] = data


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


def bits_of(value: int, count: int = 5) -> list[int]:
    return [(value >> index) & 1 for index in range(count)]


def serial_plan(register_window: int, value: int,
                start_cycle: int) -> list[tuple[int, int, int]]:
    return [(register_window, bit, start_cycle + index * 3)
            for index, bit in enumerate(bits_of(value))]


def exhaustive_vectors() -> dict[str, Any]:
    combinations = 0
    comparisons = 0
    mode_01_equivalence = 0
    for bank_count in prg_model.SUPPORTED_PRG_BANK_COUNTS:
        mapper = prg_model.MMC1PrgMapper(bank_count)
        for control in range(32):
            mapper.serial.registers[0] = control
            for register in range(32):
                mapper.serial.registers[3] = register
                produced = mapper.window_banks()
                expected = prg_reference.reference_window_banks(
                    control, register, bank_count)
                if produced != expected:
                    raise AssertionError(
                        f"window mismatch banks={bank_count} control={control:#04x} "
                        f"reg={register:#04x}: {produced} vs {expected}")
                for address in PROBE_ADDRESSES:
                    if mapper.map_offset(address) != prg_reference.reference_map_offset(
                            control, register, bank_count, address):
                        raise AssertionError(
                            f"map mismatch banks={bank_count} control={control:#04x} "
                            f"reg={register:#04x} address={address:#06x}")
                    comparisons += 1
                combinations += 1
        for register in range(32):
            mapper.serial.registers[0] = 0 << 2  # mode 0
            mapper.serial.registers[3] = register
            mode0 = mapper.window_banks()
            mapper.serial.registers[0] = 1 << 2  # mode 1
            mode1 = mapper.window_banks()
            if mode0 != mode1:
                raise AssertionError(
                    f"mode 0/1 mismatch banks={bank_count} reg={register:#04x}")
            mode_01_equivalence += 1
    return {
        "bank_counts": list(prg_model.SUPPORTED_PRG_BANK_COUNTS),
        "control_values": 32,
        "register_values": 32,
        "combinations": combinations,
        "address_comparisons": comparisons,
        "mode01_equivalence": mode_01_equivalence,
    }


def explicit_mode_checks() -> dict[str, Any]:
    checks = 0
    for bank_count in prg_model.SUPPORTED_PRG_BANK_COUNTS:
        mapper = prg_model.MMC1PrgMapper(bank_count)
        mask = bank_count - 1
        for register in range(32):
            mapper.serial.registers[3] = register
            mapper.serial.registers[0] = 2 << 2
            low, high = mapper.window_banks()
            if low != 0 or high != (register & mask):
                raise AssertionError(
                    f"mode 2 mismatch banks={bank_count} reg={register:#04x}")
            mapper.serial.registers[0] = 3 << 2
            low, high = mapper.window_banks()
            if high != bank_count - 1 or low != (register & mask):
                raise AssertionError(
                    f"mode 3 mismatch banks={bank_count} reg={register:#04x}")
            mapper.serial.registers[0] = 0
            low, high = mapper.window_banks()
            if low % 2 != 0 or high != (low + 1) % bank_count:
                raise AssertionError(
                    f"32k mismatch banks={bank_count} reg={register:#04x}")
            checks += 3
    return {"explicit_mode_checks": checks}


def main() -> int:
    parser = argparse.ArgumentParser(description="P6-03 MMC1 PRG banking gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase6/evidence/P6-03")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}

    print("=== P6-03 MMC1 PRG Banking Gate ===", flush=True)
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
        check("control-plane:stage-row", "| P6-03 |" in queue)
        check("control-plane:terminal-reserved",
              f"{TERMINAL_MARKER}=NOT_PROVEN" in queue)
        check("control-plane:compat-reserved",
              f"{COMPAT_MARKER}=NOT_PROVEN" in queue
              and f"{COMPAT_MARKER}=NOT_PROVEN" in state)

        banner("power_on_and_modes")
        default = prg_model.MMC1PrgMapper(4)
        check("power-on:mode3-fixed-last",
              default.prg_mode == 3 and default.window_banks() == (0, 3))
        check("power-on:mirroring-bits", default.mirroring == "one_screen_lower")
        check("supported:bank-counts",
              prg_model.SUPPORTED_PRG_BANK_COUNTS == (1, 2, 4, 8, 16))

        banner("exhaustive_vectors")
        vectors = exhaustive_vectors()
        check("vectors:combinations", vectors["combinations"] == 5120)
        check("vectors:address-comparisons", vectors["address_comparisons"] == 40960)
        check("vectors:mode01-equivalence", vectors["mode01_equivalence"] == 160)
        explicit = explicit_mode_checks()
        check("vectors:explicit-mode-checks",
              explicit["explicit_mode_checks"] == 480)
        FINDINGS["vectors"] = {**vectors, **explicit}

        banner("serial_integration")
        serial = serial_model.MMC1Serial()
        mapper = prg_model.MMC1PrgMapper(4, serial)
        plan = serial_plan(0x8000, 0x0F, 10) + serial_plan(0xE000, 0x02, 30)
        for step in plan:
            serial.write(*step)
        check("integration:control-mode3",
              mapper.prg_mode == 3 and mapper.mirroring == "horizontal"
              and mapper.chr_mode == 0)
        check("integration:prg-bank-2",
              mapper.prg_register == 2 and mapper.window_banks() == (2, 3))
        check("integration:map-offset",
              mapper.map_offset(0x8000) == 2 * 0x4000
              and mapper.map_offset(0xC123) == 3 * 0x4000 + 0x123
              and mapper.map_offset(0xBFFF) == 2 * 0x4000 + 0x3FFF)

        banner("fixture_configurations")
        public_rom, public_meta = fixture_build.build()
        check("fixture:public-banks", public_meta["prg_banks"] == 4)
        public_mapper = prg_model.MMC1PrgMapper(4)
        public_mapper.serial.registers[0] = 0x0F
        public_mapper.serial.registers[3] = 0
        check("fixture:public-layout",
              public_mapper.window_banks() == (0, 3))
        private_mapper = prg_model.MMC1PrgMapper(8)
        private_mapper.serial.registers[0] = 0x0F
        private_mapper.serial.registers[3] = 0
        check("fixture:private-contract-layout",
              private_mapper.window_banks() == (0, 7))
        check("fixture:rom-present", len(public_rom) > 0)

        banner("negative")
        for bank_count in (0, 3, 5, 17, 32):
            expect_fail(f"bank-count-{bank_count}",
                        lambda count=bank_count: prg_model.MMC1PrgMapper(count),
                        (prg_model.MMC1PrgError,))
        expect_fail("bank-count-bool", lambda: prg_model.MMC1PrgMapper(True),
                    (prg_model.MMC1PrgError,))
        expect_fail("bank-count-string", lambda: prg_model.MMC1PrgMapper("4"),
                    (prg_model.MMC1PrgError,))
        probe = prg_model.MMC1PrgMapper(4)
        expect_fail("address-below-window", lambda: probe.map_offset(0x7FFF),
                    (prg_model.MMC1PrgError,))
        expect_fail("address-above-window", lambda: probe.map_offset(0x10000),
                    (prg_model.MMC1PrgError,))
        expect_fail("address-bool", lambda: probe.map_offset(True),
                    (prg_model.MMC1PrgError,))
        check("negative:state-untouched",
              probe.serial.state()["registers"] == {
                  "control": 0x0C, "chr_bank_0": 0, "chr_bank_1": 0, "prg_bank": 0})

        banner("regressions")
        regressions = []
        for script, extra in (
            ("tools/test_nes_rom_v1.py", []),
            ("tools/test_nes_platform_v1.py", []),
            ("tools/test_phase6_mmc1_inventory_v1.py",
             ["--evidence-dir", ".openrecomp-phase6/scratch/P6-03/regression_p6_01"]),
            ("tools/test_phase6_mmc1_serial_v1.py",
             ["--evidence-dir", ".openrecomp-phase6/scratch/P6-03/regression_p6_02"]),
            ("tools/test_phase6_boundary_v1.py",
             ["--evidence-dir", ".openrecomp-phase6/scratch/P6-03/regression_p6_00"]),
        ):
            record = run_regression(script, extra)
            check(f"regression:{script}:exit", record["returncode"] == 0)
            check(f"regression:{script}:stderr", record["stderr_empty"])
            regressions.append(record)
        FINDINGS["regressions"] = regressions

        banner("evidence_hygiene")
        write_json("prg_banking.json", {
            "stage": STAGE,
            "claim": "MMC1_SUBSET_V1",
            "masking_rule": "bank = register & (bank_count - 1)",
            "supported_bank_counts": list(prg_model.SUPPORTED_PRG_BANK_COUNTS),
            "vectors": FINDINGS["vectors"],
            "layouts": {
                "power_on_4_banks": prg_model.MMC1PrgMapper(4).layout(),
                "public_4_banks_control_0x0f": public_mapper.layout(),
                "private_8_banks_control_0x0f": private_mapper.layout(),
            },
        })
        write_json("reference_comparison.json", {
            "stage": STAGE,
            "implementation": ".openrecomp-phase6/src/p6_mapper1_prg_v1.py",
            "reference": ".openrecomp-phase6/src/p6_mapper1_prg_reference_v1.py",
            "combinations": vectors["combinations"],
            "comparisons": vectors["address_comparisons"] + vectors["combinations"],
            "mismatches": 0,
        })
        write_json("regressions.json", {"stage": STAGE, "regressions": regressions})
        private_bytes = private_fixture.PRIVATE_ROM.read_bytes()
        for name, data in EVIDENCE_WRITES.items():
            check(f"hygiene:no-public-rom-bytes:{name}", public_rom not in data)
            check(f"hygiene:no-private-rom-bytes:{name}", private_bytes not in data)
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
    (EVIDENCE_DIR / "p6_03_tests.json").write_text(
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
