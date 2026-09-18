#!/usr/bin/env python3
"""OpenRecomp Phase-6 MMC1 CHR banking and mirroring gate (P6-04).

Differentially verifies `MMC1_SUBSET_V1` CHR mapping (8 KiB and 4 KiB modes)
and nametable mirroring (one-screen lower/upper, vertical, horizontal) against
independently structured reference models, and verifies fail-closed behaviour.

On success it emits::

    OPENRECOMP_P6_04=PASS
    OPENRECOMP_PHASE6_MMC1_CHR_V1=PASS tests=<count>
    OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase6_mmc1_chr_v1.py --evidence-dir .openrecomp-phase6/evidence/P6-04
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
import p6_mapper1_chr_reference_v1 as chr_reference  # noqa: E402
import p6_mapper1_chr_v1 as chr_model  # noqa: E402
import p6_mmc1_serial_v1 as serial_model  # noqa: E402
import p6_private_fixture_v1 as private_fixture  # noqa: E402

STAGE = "P6-04"
STAGE_MARKER = "OPENRECOMP_P6_04"
FEATURE_MARKER = "OPENRECOMP_PHASE6_MMC1_CHR_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY"

PHASE5_TAG_OBJECT = "b5d6832ba2374b810f4c24500ed9093a9481fd8d"
PHASE5_COMMIT = "e8d3627a622d0ca3196b117c5112f29fabdb49e7"
PHASE5_TREE = "468fb9788350de393d3de2ca9471b7d874ee8dc9"

CHR_PROBES = (0x0000, 0x0FFF, 0x1000, 0x1FFF, 0x0123, 0x1ABC)
MIRRORING_MODES = (0, 1, 2, 3)

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


def chr_vectors() -> dict[str, Any]:
    comparisons = 0
    mode0_combinations = 0
    mode1_combinations = 0
    for count in chr_model.SUPPORTED_CHR_BANK_COUNTS_8K:
        mapper = chr_model.MMC1Chr(count)
        for control in range(32):
            mapper.serial.registers[0] = control
            for register_0 in range(32):
                mapper.serial.registers[1] = register_0
                for address in CHR_PROBES:
                    if mapper.map_offset(address) != chr_reference.reference_chr_offset(
                            control, register_0, mapper.serial.registers[2], count,
                            address):
                        raise AssertionError(
                            f"CHR mismatch count={count} control={control:#04x} "
                            f"reg0={register_0:#04x} address={address:#06x}")
                    comparisons += 1
                mode0_combinations += 1
                for register_1 in range(32):
                    mapper.serial.registers[2] = register_1
                    for address in CHR_PROBES:
                        if mapper.map_offset(address) != chr_reference.reference_chr_offset(
                                control, register_0, register_1, count, address):
                            raise AssertionError(
                                f"CHR mismatch count={count} control={control:#04x} "
                                f"reg0={register_0:#04x} reg1={register_1:#04x} "
                                f"address={address:#06x}")
                        comparisons += 1
                    mode1_combinations += 1
                mapper.serial.registers[2] = 0
    return {
        "bank_counts": list(chr_model.SUPPORTED_CHR_BANK_COUNTS_8K),
        "chr_mode_0_combinations": mode0_combinations,
        "chr_mode_1_combinations": mode1_combinations,
        "comparisons": comparisons,
    }


def mirroring_vectors() -> dict[str, Any]:
    comparisons = 0
    per_mode: dict[str, int] = {}
    for mode in MIRRORING_MODES:
        nametables = chr_model.MMC1Nametables()
        nametables.serial.registers[0] = mode
        count = 0
        for address in range(0x2000, 0x3F00):
            if nametables.table_for_address(address) != chr_reference.reference_mirroring_table(
                    mode, address):
                raise AssertionError(
                    f"mirroring mismatch mode={mode} address={address:#06x}")
            if nametables.physical_offset(address) != chr_reference.reference_nametable_offset(
                    mode, address):
                raise AssertionError(
                    f"nametable offset mismatch mode={mode} address={address:#06x}")
            comparisons += 2
            count += 2
        per_mode[chr_model.MIRRORING_NAMES[mode]] = count
    return {"modes": per_mode, "comparisons": comparisons,
            "nametable_addresses_per_mode": 0x1F00}


def main() -> int:
    parser = argparse.ArgumentParser(description="P6-04 MMC1 CHR/mirroring gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase6/evidence/P6-04")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}

    print("=== P6-04 MMC1 CHR Banking and Mirroring Gate ===", flush=True)
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
        check("control-plane:stage-row", "| P6-04 |" in queue)
        check("control-plane:terminal-reserved",
              f"{TERMINAL_MARKER}=NOT_PROVEN" in queue)
        check("control-plane:compat-reserved",
              f"{COMPAT_MARKER}=NOT_PROVEN" in queue
              and f"{COMPAT_MARKER}=NOT_PROVEN" in state)

        banner("power_on")
        default_chr = chr_model.MMC1Chr(4)
        default_tables = chr_model.MMC1Nametables()
        check("power-on:chr-mode0-bank0",
              default_chr.chr_mode == 0 and default_chr.banks()["bank_0"] == 0)
        check("power-on:one-screen-lower",
              default_tables.mirroring == "one_screen_lower"
              and default_tables.table_for_address(0x2000) == 0
              and default_tables.table_for_address(0x2C00) == 0)
        check("supported:chr-bank-counts",
              chr_model.SUPPORTED_CHR_BANK_COUNTS_8K == (1, 2, 4, 8, 16))

        banner("chr_vectors")
        chr_stats = chr_vectors()
        check("chr:mode0-combinations", chr_stats["chr_mode_0_combinations"] == 5120)
        check("chr:mode1-combinations", chr_stats["chr_mode_1_combinations"] == 163840)
        check("chr:comparisons", chr_stats["comparisons"] == (
            5120 * len(CHR_PROBES) + 163840 * len(CHR_PROBES)))
        FINDINGS["chr_vectors"] = chr_stats

        banner("mirroring_vectors")
        mirror_stats = mirroring_vectors()
        check("mirroring:comparisons", mirror_stats["comparisons"] == 4 * 0x1F00 * 2)
        check("mirroring:one-screen-lower",
              all(chr_model.MMC1Nametables(_control(0)).table_for_address(address) == 0
                  for address in (0x2000, 0x2400, 0x2800, 0x2C00)))
        check("mirroring:one-screen-upper",
              all(chr_model.MMC1Nametables(_control(1)).table_for_address(address) == 1
                  for address in (0x2000, 0x2400, 0x2800, 0x2C00)))
        vertical = chr_model.MMC1Nametables(_control(2))
        horizontal = chr_model.MMC1Nametables(_control(3))
        check("mirroring:vertical",
              [vertical.table_for_address(address)
               for address in (0x2000, 0x2400, 0x2800, 0x2C00)] == [0, 1, 0, 1])
        check("mirroring:horizontal",
              [horizontal.table_for_address(address)
               for address in (0x2000, 0x2400, 0x2800, 0x2C00)] == [0, 0, 1, 1])
        check("mirroring:table-offsets",
              vertical.physical_offset(0x2455) == 0x400 + 0x055
              and horizontal.physical_offset(0x2855) == 0x400 + 0x055)
        FINDINGS["mirroring_vectors"] = mirror_stats

        banner("serial_integration")
        serial = serial_model.MMC1Serial()
        chr_mapper = chr_model.MMC1Chr(4, serial)
        nametables = chr_model.MMC1Nametables(serial)
        for step in (serial_plan(0x8000, 0x1F, 10)
                     + serial_plan(0xA000, 0x05, 30)
                     + serial_plan(0xC000, 0x02, 50)):
            serial.write(*step)
        check("integration:chr-mode1-banks",
              chr_mapper.chr_mode == 1 and chr_mapper.banks()["bank_0"] == 5
              and chr_mapper.banks()["bank_1"] == 2)
        check("integration:chr-offsets",
              chr_mapper.map_offset(0x0543) == 5 * 0x1000 + 0x543
              and chr_mapper.map_offset(0x1543) == 2 * 0x1000 + 0x543)
        check("integration:mirroring-horizontal",
              nametables.mirroring == "horizontal"
              and nametables.table_for_address(0x2800) == 1)

        banner("fixture_configurations")
        public_rom, public_meta = fixture_build.build()
        check("fixture:public-chr-banks", public_meta["chr_banks"] == 4)
        public_chr = chr_model.MMC1Chr(4)
        public_chr.serial.registers[0] = 0x0F
        public_chr.serial.registers[1] = 0
        check("fixture:public-chr-layout",
              public_chr.banks()["bank_0"] == 0
              and public_chr.map_offset(0x1234) == 0x1234)
        private_chr = chr_model.MMC1Chr(16)
        private_chr.serial.registers[0] = 0x0F
        private_chr.serial.registers[1] = 0
        check("fixture:private-contract-chr",
              private_chr.banks()["count"] == 16)
        check("fixture:rom-present", len(public_rom) > 0)

        banner("negative")
        for count in (0, 3, 5, 17, 32):
            expect_fail(f"chr-bank-count-{count}",
                        lambda value=count: chr_model.MMC1Chr(value),
                        (chr_model.MMC1ChrError,))
        expect_fail("chr-bank-count-bool", lambda: chr_model.MMC1Chr(True),
                    (chr_model.MMC1ChrError,))
        probe = chr_model.MMC1Chr(4)
        for address in (0x2000, 0xFFFF):
            expect_fail(f"chr-address-{address:#06x}",
                        lambda value=address: probe.map_offset(value),
                        (chr_model.MMC1ChrError,))
        expect_fail("chr-address-bool", lambda: probe.map_offset(True),
                    (chr_model.MMC1ChrError,))
        tables = chr_model.MMC1Nametables()
        for address in (0x1FFF, 0x3F00, 0x4000):
            expect_fail(f"nametable-address-{address:#06x}",
                        lambda value=address: tables.table_for_address(value),
                        (chr_model.MMC1ChrError,))
        check("negative:state-untouched",
              probe.serial.state()["registers"] == {
                  "control": 0x0C, "chr_bank_0": 0, "chr_bank_1": 0, "prg_bank": 0})

        banner("regressions")
        regressions = []
        for script, extra in (
            ("tools/test_nes_rom_v1.py", []),
            ("tools/test_nes_platform_v1.py", []),
            ("tools/test_phase6_mmc1_inventory_v1.py",
             ["--evidence-dir", ".openrecomp-phase6/scratch/P6-04/regression_p6_01"]),
            ("tools/test_phase6_mmc1_serial_v1.py",
             ["--evidence-dir", ".openrecomp-phase6/scratch/P6-04/regression_p6_02"]),
            ("tools/test_phase6_mmc1_prg_v1.py",
             ["--evidence-dir", ".openrecomp-phase6/scratch/P6-04/regression_p6_03"]),
            ("tools/test_phase6_boundary_v1.py",
             ["--evidence-dir", ".openrecomp-phase6/scratch/P6-04/regression_p6_00"]),
        ):
            record = run_regression(script, extra)
            check(f"regression:{script}:exit", record["returncode"] == 0)
            check(f"regression:{script}:stderr", record["stderr_empty"])
            regressions.append(record)
        FINDINGS["regressions"] = regressions

        banner("evidence_hygiene")
        write_json("chr_banking.json", {
            "stage": STAGE,
            "claim": "MMC1_SUBSET_V1",
            "supported_bank_counts_8k": list(chr_model.SUPPORTED_CHR_BANK_COUNTS_8K),
            "vectors": chr_stats,
            "layouts": {
                "power_on_4_banks": chr_model.MMC1Chr(4).layout(),
                "public_4_banks_control_0x0f": public_chr.layout(),
                "private_16_banks_control_0x0f": private_chr.layout(),
            },
        })
        write_json("mirroring.json", {
            "stage": STAGE,
            "claim": "MMC1_SUBSET_V1",
            "modes": {name: index for index, name
                      in chr_model.MIRRORING_NAMES.items()},
            "vectors": mirror_stats,
        })
        write_json("reference_comparison.json", {
            "stage": STAGE,
            "implementation": ".openrecomp-phase6/src/p6_mapper1_chr_v1.py",
            "reference": ".openrecomp-phase6/src/p6_mapper1_chr_reference_v1.py",
            "chr_comparisons": chr_stats["comparisons"],
            "mirroring_comparisons": mirror_stats["comparisons"],
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
    (EVIDENCE_DIR / "p6_04_tests.json").write_text(
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


def _control(mirroring_bits: int) -> serial_model.MMC1Serial:
    serial = serial_model.MMC1Serial()
    serial.registers[0] = mirroring_bits
    return serial


if __name__ == "__main__":
    raise SystemExit(main())
