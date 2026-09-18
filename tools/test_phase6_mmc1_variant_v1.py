#!/usr/bin/env python3
"""OpenRecomp Phase-6 MMC1 PRG-RAM and variant boundary gate (P6-05).

Verifies the disabled PRG-RAM window contract for the supported profile, the
explicit unsupported-variant ledger and the deterministic classification of
declared board variants. No board wiring is inferred.

On success it emits::

    OPENRECOMP_P6_05=PASS
    OPENRECOMP_PHASE6_MMC1_VARIANT_V1=PASS tests=<count>
    OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase6_mmc1_variant_v1.py --evidence-dir .openrecomp-phase6/evidence/P6-05
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
import p6_ines_v1 as ingestion  # noqa: E402
import p6_mapper1_variant_v1 as variant_model  # noqa: E402
import p6_private_fixture_v1 as private_fixture  # noqa: E402

STAGE = "P6-05"
STAGE_MARKER = "OPENRECOMP_P6_05"
FEATURE_MARKER = "OPENRECOMP_PHASE6_MMC1_VARIANT_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY"

PHASE5_TAG_OBJECT = "b5d6832ba2374b810f4c24500ed9093a9481fd8d"
PHASE5_COMMIT = "e8d3627a622d0ca3196b117c5112f29fabdb49e7"
PHASE5_TREE = "468fb9788350de393d3de2ca9471b7d874ee8dc9"

EXPECTED_VARIANT_IDS = tuple(f"V-{index:03d}" for index in range(1, 13))

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


def probe_image(rom: bytes, *, prg_banks: int | None = None,
                chr_banks: int | None = None, flags6: int | None = None,
                flags7: int | None = None, flags8: int | None = None) -> bytes:
    head = bytearray(rom[:16])
    if flags6 is not None:
        head[6] = flags6
    if flags7 is not None:
        head[7] = flags7
    if flags8 is not None:
        head[8] = flags8
    if prg_banks is not None:
        head[4] = prg_banks
    if chr_banks is not None:
        head[5] = chr_banks
    if flags7 is not None and (flags7 & 0x0C) == 0x08:
        head[9] &= 0xF0
        head[12] &= 0xFC
    total = head[4] * 0x4000 + head[5] * 0x2000
    seed = bytes(rom[16:16 + min(total, len(rom) - 16)])
    body = bytearray(seed)
    while len(body) < total:
        body.append((len(body) * 7 + 1) & 0xFF)
    return bytes(head) + bytes(body[:total])


def main() -> int:
    parser = argparse.ArgumentParser(description="P6-05 MMC1 PRG-RAM/variant gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase6/evidence/P6-05")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}

    print("=== P6-05 MMC1 PRG-RAM and Variant Boundary Gate ===", flush=True)
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
        check("control-plane:stage-row", "| P6-05 |" in queue)
        check("control-plane:terminal-reserved",
              f"{TERMINAL_MARKER}=NOT_PROVEN" in queue)
        check("control-plane:compat-reserved",
              f"{COMPAT_MARKER}=NOT_PROVEN" in queue
              and f"{COMPAT_MARKER}=NOT_PROVEN" in state)

        banner("prg_ram_contract")
        public_rom, public_meta = fixture_build.build()
        public_doc = ingestion.ingest(public_rom, source_label="public_fixture")
        public_window = variant_model.MMC1PrgRamWindow(public_doc)
        check("prg-ram:public-disabled",
              public_window.present() is False
              and public_window.declared_bytes == 0
              and public_window.battery is False)
        check("prg-ram:status", public_window.status()["profile"]
              == variant_model.SUPPORTED_PROFILE)
        private_doc = ingestion.ingest_path(private_fixture.PRIVATE_ROM,
                                            source_label="private_tmnt")
        private_window = variant_model.MMC1PrgRamWindow(private_doc)
        check("prg-ram:private-disabled",
              private_window.present() is False
              and private_window.declared_bytes == 0
              and private_window.battery is False)
        for address in (variant_model.PRG_RAM_BASE, 0x7000, variant_model.PRG_RAM_END):
            expect_fail(f"prg-ram-read-{address:#06x}",
                        lambda value=address: public_window.read(value),
                        (variant_model.MMC1PrgRamError,))
        expect_fail("prg-ram-write",
                    lambda: public_window.write(0x6000, 0x5A),
                    (variant_model.MMC1PrgRamError,))
        expect_fail("prg-ram-write-bad-value",
                    lambda: public_window.write(0x6000, 0x100),
                    (variant_model.MMC1PrgRamError,))
        expect_fail("prg-ram-address-below",
                    lambda: public_window.read(0x5FFF),
                    (variant_model.MMC1PrgRamError,))
        expect_fail("prg-ram-address-above",
                    lambda: public_window.read(0x8000),
                    (variant_model.MMC1PrgRamError,))
        expect_fail("prg-ram-address-bool",
                    lambda: public_window.read(True),
                    (variant_model.MMC1PrgRamError,))
        expect_fail("prg-ram-declared-ram",
                    lambda: variant_model.MMC1PrgRamWindow({"prg_ram_bytes": 8192}),
                    (variant_model.MMC1PrgRamError,))
        expect_fail("prg-ram-battery",
                    lambda: variant_model.MMC1PrgRamWindow({"prg_ram_bytes": 0,
                                                            "battery": True}),
                    (variant_model.MMC1PrgRamError,))
        expect_fail("prg-ram-inventory-type",
                    lambda: variant_model.MMC1PrgRamWindow(["not", "a", "doc"]),
                    (variant_model.MMC1PrgRamError,))
        FINDINGS["prg_ram_status"] = public_window.status()

        banner("variant_ledger")
        ledger = variant_model.variant_ledger()
        check("ledger:ids",
              tuple(entry["id"] for entry in ledger) == EXPECTED_VARIANT_IDS)
        check("ledger:statuses",
              all(entry["status"] in variant_model.VARIANT_STATUSES
                  for entry in ledger))
        check("ledger:basis",
              all(entry["name"] and entry["requirement"] and entry["basis"]
                  for entry in ledger))
        check("ledger:supported-profile",
              [entry["id"] for entry in ledger if entry["status"] == "SUPPORTED"]
              == ["V-001"])
        check("ledger:not-tested",
              [entry["id"] for entry in ledger if entry["status"] == "NOT_TESTED"]
              == ["V-011"])

        banner("variant_classification")
        public_variant = variant_model.classify_variant(public_doc)
        private_variant = variant_model.classify_variant(private_doc)
        check("variant:public-supported",
              public_variant["status"] == "SUPPORTED_PROFILE"
              and public_variant["variant_labels"] == [])
        check("variant:private-supported",
              private_variant["status"] == "SUPPORTED_PROFILE"
              and private_variant["variant_labels"] == [])
        cases = [
            ("battery", probe_image(public_rom, flags6=0x12), "BLOCKED_UNSUPPORTED_MMC1_VARIANT",
             "PRG-RAM/battery board"),
            ("prg-ram", probe_image(public_rom, flags8=1), "BLOCKED_UNSUPPORTED_MMC1_VARIANT",
             "PRG-RAM/battery board"),
            ("chr-ram", probe_image(public_rom, chr_banks=0), "BLOCKED_UNSUPPORTED_MMC1_VARIANT",
             "CHR-RAM board"),
            ("submapper", probe_image(public_rom, flags7=0x08, flags8=0x10),
             "BLOCKED_UNSUPPORTED_MMC1_VARIANT", "non-zero submapper variant"),
            ("four-screen", probe_image(public_rom, flags6=0x18),
             "BLOCKED_UNSUPPORTED_MMC1_VARIANT", "four-screen board"),
            ("vs-unisystem", probe_image(public_rom, flags7=0x01),
             "BLOCKED_UNSUPPORTED_MMC1_VARIANT", "VS UniSystem board"),
            ("playchoice", probe_image(public_rom, flags7=0x02),
             "BLOCKED_UNSUPPORTED_MMC1_VARIANT", "PlayChoice board"),
            ("prg-banks-3", probe_image(public_rom, prg_banks=3),
             "BLOCKED_UNSUPPORTED_MMC1_VARIANT", "non-power-of-two PRG wiring"),
            ("chr-banks-3", probe_image(public_rom, chr_banks=3),
             "BLOCKED_UNSUPPORTED_MMC1_VARIANT", "non-power-of-two CHR wiring"),
            ("prg-banks-32", probe_image(public_rom, prg_banks=32),
             "BLOCKED_UNSUPPORTED_MMC1_VARIANT", "PRG size outside the supported range"),
            ("mapper-2", probe_image(public_rom, flags6=0x20),
             "BLOCKED_UNSUPPORTED_MAPPER", None),
        ]
        classification_records = []
        for label, image, expected_status, expected_label in cases:
            document = ingestion.ingest(image, source_label=f"variant_{label}")
            report = variant_model.classify_variant(document)
            if report["status"] != expected_status:
                raise AssertionError(
                    f"variant {label}: {report['status']} != {expected_status}")
            if expected_label is not None and expected_label not in report["variant_labels"]:
                raise AssertionError(
                    f"variant {label}: {report['variant_labels']} missing "
                    f"{expected_label!r}")
            classification_records.append({
                "case": label, "status": report["status"],
                "labels": report["variant_labels"],
            })
            check(f"variant:{label}",
                  report["status"] == expected_status)
        FINDINGS["variant_classes"] = classification_records

        banner("regressions")
        regressions = []
        for script, extra in (
            ("tools/test_nes_rom_v1.py", []),
            ("tools/test_nes_platform_v1.py", []),
            ("tools/test_phase6_mmc1_inventory_v1.py",
             ["--evidence-dir", ".openrecomp-phase6/scratch/P6-05/regression_p6_01"]),
            ("tools/test_phase6_mmc1_serial_v1.py",
             ["--evidence-dir", ".openrecomp-phase6/scratch/P6-05/regression_p6_02"]),
            ("tools/test_phase6_mmc1_prg_v1.py",
             ["--evidence-dir", ".openrecomp-phase6/scratch/P6-05/regression_p6_03"]),
            ("tools/test_phase6_mmc1_chr_v1.py",
             ["--evidence-dir", ".openrecomp-phase6/scratch/P6-05/regression_p6_04"]),
            ("tools/test_phase6_boundary_v1.py",
             ["--evidence-dir", ".openrecomp-phase6/scratch/P6-05/regression_p6_00"]),
        ):
            record = run_regression(script, extra)
            check(f"regression:{script}:exit", record["returncode"] == 0)
            check(f"regression:{script}:stderr", record["stderr_empty"])
            regressions.append(record)
        FINDINGS["regressions"] = regressions

        banner("evidence_hygiene")
        write_json("prg_ram.json", {
            "stage": STAGE,
            "claim": "MMC1_SUBSET_V1",
            "supported_profile": variant_model.SUPPORTED_PROFILE,
            "window": [variant_model.PRG_RAM_BASE, variant_model.PRG_RAM_END],
            "public_status": public_window.status(),
            "private_status": private_window.status(),
        })
        write_json("variants.json", {
            "stage": STAGE,
            "ledger": ledger,
            "public_classification": public_variant,
            "private_classification": private_variant,
            "probes": classification_records,
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
    (EVIDENCE_DIR / "p6_05_tests.json").write_text(
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
