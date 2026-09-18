#!/usr/bin/env python3
"""OpenRecomp Phase-6 public MMC1 proof fixture gate (P6-06).

Verifies the deterministic build and recorded identity of the full behavioural
public MMC1 proof fixture, its static behavioural inventory (PRG/CHR/mirroring
register writes, PPU use, controller input, graphics setup, run-exit thunk) and
that its intended MMC1 register sequences exercise the supported contract when
replayed through the P6-02 .. P6-05 mapper models. The P6-01 established
fixture identity remains frozen and is re-verified.

On success it emits::

    OPENRECOMP_P6_06=PASS
    OPENRECOMP_PHASE6_MMC1_FIXTURE_V1=PASS tests=<count>
    OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase6_mmc1_fixture_v1.py --evidence-dir .openrecomp-phase6/evidence/P6-06
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

import p6_fixture_build_v1 as base_fixture  # noqa: E402
import p6_fixture_proof_v1 as proof_fixture  # noqa: E402
import p6_ines_v1 as ingestion  # noqa: E402
import p6_mapper1_chr_v1 as chr_model  # noqa: E402
import p6_mapper1_prg_v1 as prg_model  # noqa: E402
import p6_mapper1_variant_v1 as variant_model  # noqa: E402
import p6_mmc1_serial_v1 as serial_model  # noqa: E402
import p6_private_fixture_v1 as private_fixture  # noqa: E402

STAGE = "P6-06"
STAGE_MARKER = "OPENRECOMP_P6_06"
FEATURE_MARKER = "OPENRECOMP_PHASE6_MMC1_FIXTURE_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY"

PHASE5_TAG_OBJECT = "b5d6832ba2374b810f4c24500ed9093a9481fd8d"
PHASE5_COMMIT = "e8d3627a622d0ca3196b117c5112f29fabdb49e7"
PHASE5_TREE = "468fb9788350de393d3de2ca9471b7d874ee8dc9"

BASE_ROM_SHA256 = "7d5514c7db89ae9be5cb98bc8c12f94761d187e2a52a28018fa87f0af971d833"
PROOF_ROM_SHA256 = "9e10dce532266592f9ccda781bc6d3a7354ab4951bd3db87e4f43d1c45056b70"
PROOF_ROM_SIZE = 98320
PROOF_HEADER_HEX = "4e45531a040410000000000000000000"
PROOF_PRG_SHA256 = "197a464f5ffe038b225b038aac928e75b7f9daa19bd93f476ad7b6666bd2c486"
PROOF_CHR_SHA256 = "4f9abd22d246d0f3d691e0ec7379f61b88c34b5653d6a8299f2fc73e287ad9fd"
PROOF_PRG_BANK_SHA256 = (
    "e12ec00b3378ef16c2855d72330870c8249f20245372db1e9d931c7e04fabf73",
    "da5341ea7df3d88175e33abf30538251d94989d540fb6bf5e6f5a2af3ef38c90",
    "569ee4a0b2876656a9aa395b87ac2850e426fba567d8de4d9d1934e03cf3a10e",
    "4772b3c97b2e70c823c5111cd40370a06d8a8b224b3e1167df8aab405b66643d",
)
PROOF_VECTORS = {"nmi": 0xC1F8, "reset": 0xC000, "irq": 0xC235}
PROOF_INSTRUCTIONS = 262
PROOF_SOURCE_SHA256 = "17f12ba0cb7b5d5a220ed205b28e66ff62e33959b8e62f47dae9c598fa533528"
PROOF_ASSEMBLER_SHA256 = "dd82b6a46b3c0411b9977677254b2796b5a6161da8fe544588df13b7d444ce80"
PROOF_MMC1_WINDOWS = ("0x8000", "0xa000", "0xc000", "0xe000")
PROOF_PPU_WRITES = ("0x2000", "0x2001", "0x2003", "0x2004", "0x2005",
                    "0x2006", "0x2007", "0x4014")
PROOF_PPU_READS = ("0x2002", "0x2007")
PROOF_SWITCHABLE_READS = ("0x8000", "0x8100")

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


def main() -> int:
    parser = argparse.ArgumentParser(description="P6-06 MMC1 proof fixture gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase6/evidence/P6-06")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}

    print("=== P6-06 Public MMC1 Proof Fixture Gate ===", flush=True)
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
        check("control-plane:stage-row", "| P6-06 |" in queue)
        check("control-plane:terminal-reserved",
              f"{TERMINAL_MARKER}=NOT_PROVEN" in queue)
        check("control-plane:compat-reserved",
              f"{COMPAT_MARKER}=NOT_PROVEN" in queue
              and f"{COMPAT_MARKER}=NOT_PROVEN" in state)

        banner("established_fixture_frozen")
        base_rom, base_meta = base_fixture.build()
        check("base:identity-preserved",
              base_meta["rom_sha256"] == BASE_ROM_SHA256)

        banner("proof_fixture_build")
        proof_rom, proof_meta = proof_fixture.build_proof()
        proof_rom_2, proof_meta_2 = proof_fixture.build_proof()
        check("proof:build-byte-identical", proof_rom == proof_rom_2)
        check("proof:metadata-identical", proof_meta == proof_meta_2)
        check("base:distinct-from-proof", base_rom != proof_rom)
        check("proof:rom-size", len(proof_rom) == PROOF_ROM_SIZE)
        check("proof:rom-sha256", proof_meta["rom_sha256"] == PROOF_ROM_SHA256)
        check("proof:source-sha256",
              proof_meta["source_sha256"] == PROOF_SOURCE_SHA256)
        check("proof:assembler-sha256",
              proof_meta["assembler_sha256"] == PROOF_ASSEMBLER_SHA256)
        check("proof:header", proof_meta["header_hex"] == PROOF_HEADER_HEX)
        check("proof:prg",
              proof_meta["prg_sha256"] == PROOF_PRG_SHA256
              and proof_meta["prg_size"] == 65536
              and proof_meta["prg_banks"] == 4)
        check("proof:prg-bank-hashes",
              tuple(proof_meta["prg_bank_sha256"]) == PROOF_PRG_BANK_SHA256)
        check("proof:chr",
              proof_meta["chr_sha256"] == PROOF_CHR_SHA256
              and proof_meta["chr_size"] == 32768
              and proof_meta["chr_banks"] == 4)
        check("proof:mapper-metadata",
              proof_meta["mapper"] == 1 and proof_meta["submapper"] == 0
              and proof_meta["mirroring"] == "horizontal"
              and proof_meta["power_on_control"] == 0x0C)
        check("proof:vectors", proof_meta["vectors"] == PROOF_VECTORS)
        check("proof:instruction-count",
              proof_meta["instruction_count"] == PROOF_INSTRUCTIONS
              and proof_meta["instructions_cross_checked"] == PROOF_INSTRUCTIONS)
        check("proof:license", proof_meta["origin"] == "original"
              and proof_meta["license"] == "Apache-2.0")
        check("proof:labels",
              proof_meta["labels"]["reset"] == 0xC000
              and proof_meta["labels"]["nmi_handler"] == PROOF_VECTORS["nmi"]
              and proof_meta["labels"]["irq_handler"] == PROOF_VECTORS["irq"])

        banner("behaviour_inventory")
        behaviour = proof_meta["behaviour"]
        check("behaviour:mmc1-windows",
              tuple(behaviour["mmc1_write_windows"]) == PROOF_MMC1_WINDOWS)
        check("behaviour:ppu-writes",
              tuple(behaviour["ppu_writes"]) == PROOF_PPU_WRITES)
        check("behaviour:ppu-reads",
              tuple(behaviour["ppu_reads"]) == PROOF_PPU_READS)
        check("behaviour:controller-reads",
              tuple(behaviour["controller_reads"]) == ("0x4016",)
              and behaviour["writes"]["0x4016"] == 2)
        check("behaviour:switchable-reads",
              tuple(behaviour["switchable_window_reads"]) == PROOF_SWITCHABLE_READS)
        check("behaviour:exit-thunk",
              tuple(behaviour["exit_thunk"]) == ("0x02ff",))
        check("behaviour:opcode-forms", behaviour["opcode_form_count"] == 40)
        check("behaviour:graphics-setup",
              all(name in proof_meta["labels"] for name in
                  ("load_palette", "load_nametable", "setup_sprites",
                   "wait_vblank")))
        FINDINGS["behaviour"] = behaviour

        banner("proof_ingestion")
        proof_doc = ingestion.ingest(proof_rom, source_label="proof_fixture")
        check("proof:ingest-status",
              proof_doc["phase6"]["status"] == "SUPPORTED_MMC1"
              and proof_doc["phase6"]["prg_banks_16k"] == 4
              and proof_doc["phase6"]["chr_banks_8k"] == 4)
        check("proof:ingest-vectors",
              proof_doc["vectors"] == PROOF_VECTORS
              and proof_doc["vectors_source"] == "mmc1_power_on_fixed_last_bank")
        check("proof:ingest-container", proof_doc["container"] == "ines")
        proof_window = variant_model.MMC1PrgRamWindow(proof_doc)
        check("proof:prg-ram-disabled", proof_window.present() is False)

        banner("mapper_contract_exercise")
        serial = serial_model.MMC1Serial()
        prg = prg_model.MMC1PrgMapper(4, serial)
        for step in serial_plan(0xE000, 2, 100):
            serial.write(*step)
        check("exercise:prg-mode3",
              prg.prg_mode == 3 and prg.window_banks() == (2, 3)
              and prg.map_offset(0x8000) == 2 * 0x4000)
        serial_plans = []
        serial2 = serial_model.MMC1Serial()
        prg2 = prg_model.MMC1PrgMapper(4, serial2)
        for bank in range(4):
            for step in serial_plan(0xE000, bank, 1000 + bank * 100):
                serial2.write(*step)
            if prg2.window_banks() != (bank, 3):
                raise AssertionError(f"PRG exercise bank {bank} mismatch")
            serial_plans.append({"bank": bank, "windows": list(prg2.window_banks())})
        check("exercise:prg-banks-0-3",
              [record["windows"] for record in serial_plans]
              == [[0, 3], [1, 3], [2, 3], [3, 3]])

        serial3 = serial_model.MMC1Serial()
        chr = chr_model.MMC1Chr(4, serial3)
        for step in serial_plan(0x8000, 0x1F, 3000):
            serial3.write(*step)
        chr_records = []
        for bank in range(8):
            for step in serial_plan(0xA000, bank, 3100 + bank * 100):
                serial3.write(*step)
            for step in serial_plan(0xC000, bank, 3150 + bank * 100):
                serial3.write(*step)
            layout = chr.banks()
            if layout["bank_0"] != bank or layout["bank_1"] != bank:
                raise AssertionError(f"CHR exercise bank {bank} mismatch")
            chr_records.append(bank)
        check("exercise:chr-4k-banks-0-7",
              chr_records == list(range(8)) and chr.chr_mode == 1)

        serial4 = serial_model.MMC1Serial()
        nametables = chr_model.MMC1Nametables(serial4)
        mirror_records = []
        for mode in range(4):
            for step in serial_plan(0x8000, mode | 0x1C, 4000 + mode * 100):
                serial4.write(*step)
            mirror_records.append([
                nametables.mirroring,
                nametables.table_for_address(0x2400),
                nametables.table_for_address(0x2C00),
            ])
        check("exercise:mirroring-modes",
              mirror_records == [
                  ["one_screen_lower", 0, 0],
                  ["one_screen_upper", 1, 1],
                  ["vertical", 1, 1],
                  ["horizontal", 0, 1],
              ])
        FINDINGS["mapper_exercise"] = {
            "prg_switch_plan": serial_plans,
            "chr_4k_banks": chr_records,
            "mirroring_records": mirror_records,
        }

        banner("negative")
        source = proof_fixture.ASM_PATH.read_text(encoding="utf-8")
        expect_fail("unsupported-mnemonic",
                    lambda: proof_fixture.build_from_source(
                        source.replace("        rti", "        lax", 1)),
                    (proof_fixture.ProofFixtureBuildError,))
        expect_fail("missing-reset-label",
                    lambda: proof_fixture.build_from_source(
                        source.replace("reset:", "start:", 1)),
                    (proof_fixture.ProofFixtureBuildError,))
        expect_fail("broken-vector",
                    lambda: proof_fixture.build_from_source(
                        source.replace(".word nmi_handler", ".word $0000")),
                    (proof_fixture.ProofFixtureBuildError,))

        banner("regressions")
        regressions = []
        for script, extra in (
            ("tools/test_nes_rom_v1.py", []),
            ("tools/test_nes_platform_v1.py", []),
            ("tools/test_phase6_mmc1_inventory_v1.py",
             ["--evidence-dir", ".openrecomp-phase6/scratch/P6-06/regression_p6_01"]),
            ("tools/test_phase6_mmc1_serial_v1.py",
             ["--evidence-dir", ".openrecomp-phase6/scratch/P6-06/regression_p6_02"]),
            ("tools/test_phase6_mmc1_prg_v1.py",
             ["--evidence-dir", ".openrecomp-phase6/scratch/P6-06/regression_p6_03"]),
            ("tools/test_phase6_mmc1_chr_v1.py",
             ["--evidence-dir", ".openrecomp-phase6/scratch/P6-06/regression_p6_04"]),
            ("tools/test_phase6_mmc1_variant_v1.py",
             ["--evidence-dir", ".openrecomp-phase6/scratch/P6-06/regression_p6_05"]),
            ("tools/test_phase6_boundary_v1.py",
             ["--evidence-dir", ".openrecomp-phase6/scratch/P6-06/regression_p6_00"]),
        ):
            record = run_regression(script, extra)
            check(f"regression:{script}:exit", record["returncode"] == 0)
            check(f"regression:{script}:stderr", record["stderr_empty"])
            regressions.append(record)
        FINDINGS["regressions"] = regressions

        banner("evidence_hygiene")
        write_json("proof_fixture.json", {
            "stage": STAGE,
            "claim": "MMC1_SUBSET_V1",
            "metadata": proof_meta,
            "ingestion": proof_doc,
            "established_fixture": {
                "rom_sha256": base_meta["rom_sha256"],
                "note": "P6-01 established fixture remains frozen",
            },
        })
        write_json("behaviours.json", {
            "stage": STAGE,
            "behaviour": behaviour,
            "mapper_exercise": FINDINGS["mapper_exercise"],
        })
        write_json("regressions.json", {"stage": STAGE, "regressions": regressions})
        private_bytes = private_fixture.PRIVATE_ROM.read_bytes()
        for name, data in EVIDENCE_WRITES.items():
            check(f"hygiene:no-public-rom-bytes:{name}", proof_rom not in data)
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
    (EVIDENCE_DIR / "p6_06_tests.json").write_text(
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
