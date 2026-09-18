#!/usr/bin/env python3
"""OpenRecomp Phase-6 MMC1 requirements and fixture inventory gate (P6-01).

Verifies the bounded MMC1 supported-subset definition, the original Apache-2.0
public MMC1 fixture build and inventory, private TMNT metadata/hash inventory
(never copied) and the fail-closed classifications for malformed/unsupported
cartridge declarations.

On success it emits::

    OPENRECOMP_P6_01=PASS
    OPENRECOMP_PHASE6_MMC1_INVENTORY_V1=PASS tests=<count>
    OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase6_mmc1_inventory_v1.py --evidence-dir .openrecomp-phase6/evidence/P6-01
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

import nes_rom_v1 as frozen_rom  # noqa: E402
import p5_ines_v1 as phase5_ingestion  # noqa: E402
import p6_fixture_build_v1 as fixture_build  # noqa: E402
import p6_ines_v1 as ingestion  # noqa: E402
import p6_mmc1_spec_v1 as mmc1_spec  # noqa: E402
import p6_private_fixture_v1 as private_fixture  # noqa: E402

STAGE = "P6-01"
STAGE_MARKER = "OPENRECOMP_P6_01"
FEATURE_MARKER = "OPENRECOMP_PHASE6_MMC1_INVENTORY_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY"

PHASE5_TAG_OBJECT = "b5d6832ba2374b810f4c24500ed9093a9481fd8d"
PHASE5_COMMIT = "e8d3627a622d0ca3196b117c5112f29fabdb49e7"
PHASE5_TREE = "468fb9788350de393d3de2ca9471b7d874ee8dc9"

PUBLIC_ROM_SHA256 = "7d5514c7db89ae9be5cb98bc8c12f94761d187e2a52a28018fa87f0af971d833"
PUBLIC_ROM_SIZE = 98320
PUBLIC_HEADER_HEX = "4e45531a040410000000000000000000"
PUBLIC_PRG_SHA256 = "2fc4064ee37bd3065a39748464191e7b97c2bc2f9b2f64aa0173a5a9b4626e7f"
PUBLIC_PRG_SIZE = 65536
PUBLIC_CHR_SHA256 = "4f9abd22d246d0f3d691e0ec7379f61b88c34b5653d6a8299f2fc73e287ad9fd"
PUBLIC_CHR_SIZE = 32768
PUBLIC_VECTORS = {"nmi": 0xC029, "reset": 0xC000, "irq": 0xC02C}
PUBLIC_INSTRUCTIONS = 57
PUBLIC_PRG_BANK_SHA256 = (
    "5b6ea7c5179c6248bac436ab91d98a5c9ccbb67c64e21c6b1248c526df2b7d5b",
    "713bef4fdcb7d3c305c7d402d9dfa3c30dc9447d0c9efa3fc26968196e19d9ca",
    "94a502e63cb2644d41bcd663d9d7b99f738ac354f8e0eff4f8e033acc84f4a89",
    "9c50fbc6491043c0d81800eab9482f1df2d922be57a01d6bd3825ff1bbbbf86b",
)
PUBLIC_LABELS = {
    "reset": 0xC000,
    "main_loop": 0xC019,
    "nmi_handler": 0xC029,
    "irq_handler": 0xC02C,
}
PUBLIC_FINGERPRINT = "0f985869fd3fa7366f045be4943535a39ba666a3fdd1f90f708197939a93141d"

PRIVATE_ROM_SHA256 = "2a9345e608ec0c57470dc6658ce8199ddea9c18076134d9ef2a56f91b0a066d1"
PRIVATE_ROM_SIZE = 262160
PRIVATE_PRG_SHA256 = "2fbc367a453504f01d7dec9fcc52c59b249fd8633ee8e5de6c7ec04abe0131bc"
PRIVATE_CHR_SHA256 = "f9e354d57423f5d883663ed56801066ce38ab1a64065a735db88d42aee6eac29"

EXPECTED_REQUIREMENT_IDS = (
    "CHR-001", "CHR-002", "CHR-003", "CTRL-001", "CTRL-002", "CTRL-003",
    "IRQ-001", "MAP-001", "MAP-002", "MAP-003", "PRG-001", "PRG-002",
    "PRG-003", "PRG-004", "PRG-005", "RAM-001", "REG-001", "REG-002",
    "REG-003", "REG-004", "REG-005", "VAR-001", "VAR-002", "VAR-003",
    "VAR-004", "VAR-005",
)

REGRESSIONS = (
    "tools/test_nes_rom_v1.py",
    "tools/test_nes_platform_v1.py",
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


def run_regression(script: str) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(ROOT / script)], cwd=str(ROOT), capture_output=True)
    return {
        "script": script,
        "returncode": completed.returncode,
        "stdout_bytes": len(completed.stdout),
        "stdout_sha256_raw": sha256_bytes(completed.stdout),
        "stdout_sha256_lf": sha256_bytes(lf_normalize(completed.stdout)),
        "stderr_bytes": len(completed.stderr),
        "stderr_empty": len(completed.stderr) == 0,
    }


def _field_probe(rom: bytes, *, prg_banks: int | None = None,
                 chr_banks: int | None = None, flags6: int | None = None,
                 flags7: int | None = None, flags8: int | None = None) -> bytes:
    """Build an exact-size probe image with the requested header fields."""
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
    payload = bytes(rom[16:16 + 0x4000 * 4 + 0x2000 * 4])
    prg_size = head[4] * 0x4000
    chr_size = head[5] * 0x2000
    base = bytearray(payload[:prg_size])
    while len(base) < prg_size:
        base.append(len(base) & 0xFF)
    return bytes(head) + bytes(base) + bytes(chr_size)


def main() -> int:
    parser = argparse.ArgumentParser(description="P6-01 MMC1 inventory gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase6/evidence/P6-01")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}

    print("=== P6-01 MMC1 Requirements and Fixture Inventory Gate ===", flush=True)
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
        check("control-plane:stage-row", "| P6-01 |" in queue)
        check("control-plane:terminal-reserved",
              f"{TERMINAL_MARKER}=NOT_PROVEN" in queue)
        check("control-plane:compat-reserved",
              f"{COMPAT_MARKER}=NOT_PROVEN" in queue
              and f"{COMPAT_MARKER}=NOT_PROVEN" in state)

        banner("mmc1_subset")
        subset = mmc1_spec.subset_document()
        check("subset:claim", subset["claim"] == "MMC1_SUBSET_V1")
        check("subset:mapper", subset["mapper"] == 1)
        check("subset:serial-bits", subset["serial_bits"] == 5)
        check("subset:registers",
              [entry["name"] for entry in subset["registers"]]
              == ["control", "chr_bank_0", "chr_bank_1", "prg_bank"])
        check("subset:register-windows",
              all(entry["cpu_min"] < entry["cpu_max"] for entry in subset["registers"])
              and subset["registers"][0]["cpu_min"] == 0x8000)
        check("subset:mirroring", sorted(subset["mirroring"]) == [0, 1, 2, 3])
        check("subset:prg-modes", sorted(subset["prg_modes"]) == [0, 1, 2, 3])
        check("subset:chr-modes", sorted(subset["chr_modes"]) == [0, 1])
        check("subset:power-on", subset["power_on"]["control"] == 0x0C
              and subset["power_on"]["prg_mode"] == 3
              and subset["power_on"]["chr_mode"] == 0
              and subset["power_on"]["mirroring"] == "one_screen_lower")
        check("subset:limits", subset["limits"]["prg_bank_bytes"] == 0x4000
              and subset["limits"]["chr_bank_bytes"] == 0x2000
              and subset["limits"]["max_prg_bytes"] == 0x40000
              and subset["limits"]["max_chr_rom_bytes"] == 0x20000)
        requirements = subset["requirements"]
        check("subset:requirements-ids",
              tuple(sorted(entry["id"] for entry in requirements))
              == tuple(sorted(EXPECTED_REQUIREMENT_IDS)))
        check("subset:requirements-statuses",
              all(entry["status"] in mmc1_spec.REQUIREMENT_STATUSES
                  for entry in requirements))
        check("subset:requirements-basis",
              all(entry["basis"] for entry in requirements))
        check("subset:unsupported-variants",
              {entry["id"] for entry in requirements if entry["status"] == "UNSUPPORTED"}
              == {"VAR-001", "VAR-002", "VAR-003", "VAR-004", "VAR-005"})
        check("subset:supported-areas",
              {entry["area"] for entry in requirements if entry["status"] == "SUPPORTED"}
              == {"mapper", "serial", "control", "prg_banking", "chr_banking",
                  "prg_ram", "interrupts"})

        banner("public_fixture_build")
        rom_a, meta_a = fixture_build.build()
        rom_b, meta_b = fixture_build.build()
        check("public:build-byte-identical", rom_a == rom_b)
        check("public:metadata-identical", meta_a == meta_b)
        check("public:rom-size", len(rom_a) == PUBLIC_ROM_SIZE)
        check("public:rom-sha256", meta_a["rom_sha256"] == PUBLIC_ROM_SHA256)
        check("public:header", meta_a["header_hex"] == PUBLIC_HEADER_HEX)
        check("public:prg", meta_a["prg_sha256"] == PUBLIC_PRG_SHA256
              and meta_a["prg_size"] == PUBLIC_PRG_SIZE
              and meta_a["prg_banks"] == 4)
        check("public:prg-bank-hashes",
              tuple(meta_a["prg_bank_sha256"]) == PUBLIC_PRG_BANK_SHA256)
        check("public:chr", meta_a["chr_sha256"] == PUBLIC_CHR_SHA256
              and meta_a["chr_size"] == PUBLIC_CHR_SIZE
              and meta_a["chr_banks"] == 4)
        check("public:mapper-mirroring", meta_a["mapper"] == 1
              and meta_a["mirroring"] == "horizontal")
        check("public:fixed-bank", meta_a["fixed_bank_index"] == 3
              and meta_a["fixed_bank_origin"] == 0xC000)
        check("public:vectors", meta_a["vectors"] == PUBLIC_VECTORS)
        check("public:labels",
              all(meta_a["labels"].get(name) == value
                  for name, value in PUBLIC_LABELS.items()))
        check("public:instruction-count",
              meta_a["instruction_count"] == PUBLIC_INSTRUCTIONS)
        check("public:instructions-cross-checked",
              meta_a["instructions_cross_checked"] == PUBLIC_INSTRUCTIONS)
        check("public:original-license",
              meta_a["origin"] == "original" and meta_a["license"] == "Apache-2.0")
        check("public:register-writes",
              all(meta_a["labels"].get(name) == value for name, value in (
                  ("MMC1_CTRL_WINDOW", 0x8000), ("MMC1_CHR0_WINDOW", 0xA000),
                  ("MMC1_CHR1_WINDOW", 0xC000), ("MMC1_PRG_WINDOW", 0xE000))))

        banner("public_ingestion")
        doc_public = ingestion.ingest(rom_a, source_label="public_fixture")
        check("public:ingest-mapper", doc_public["mapper"] == 1)
        check("public:ingest-container", doc_public["container"] == "ines")
        check("public:ingest-sizes",
              doc_public["prg_bytes"] == PUBLIC_PRG_SIZE
              and doc_public["chr_bytes"] == PUBLIC_CHR_SIZE)
        check("public:ingest-exact-size",
              doc_public["actual_size"] == doc_public["declared_size"] == PUBLIC_ROM_SIZE)
        check("public:ingest-status",
              doc_public["phase6"]["status"] == "SUPPORTED_MMC1"
              and doc_public["phase6"]["prg_banks_16k"] == 4
              and doc_public["phase6"]["chr_banks_8k"] == 4)
        check("public:ingest-vectors", doc_public["vectors"] == PUBLIC_VECTORS
              and doc_public["vectors_source"] == "mmc1_power_on_fixed_last_bank")
        check("public:ingest-fingerprint-stable",
              ingestion.fingerprint(doc_public) == PUBLIC_FINGERPRINT)
        check("public:phase5-status-preserved",
              doc_public["execution_status"] == "BLOCKED_UNSUPPORTED_MAPPER")
        frozen_classification = frozen_rom.classify(rom_a)
        check("public:frozen-classify",
              frozen_classification.mapper == 1
              and frozen_classification.prg_bytes == PUBLIC_PRG_SIZE
              and frozen_classification.chr_bytes == PUBLIC_CHR_SIZE)
        expect_fail("public:frozen-mapper-fail-closed",
                    lambda: frozen_rom.make_mapper(rom_a),
                    (frozen_rom.NESROMError,))
        phase5_doc = phase5_ingestion.ingest(rom_a, source_label="public_fixture").to_document()
        check("public:phase5-vectors-unavailable",
              phase5_doc["vectors"] is None
              and phase5_doc["execution_status"] == "BLOCKED_UNSUPPORTED_MAPPER")

        banner("private_fixture")
        private = private_fixture.inventory()
        check("private:sha256", private["image_sha256"] == PRIVATE_ROM_SHA256)
        check("private:size", private["image_size"] == PRIVATE_ROM_SIZE)
        check("private:container", private["container"] == "nes2.0")
        check("private:mapper", private["mapper"] == 1
              and private["submapper"] == 0)
        check("private:mirroring", private["mirroring"] == "horizontal")
        check("private:prg-chr",
              private["prg_bytes"] == 0x20000 and private["chr_bytes"] == 0x20000)
        check("private:hashes",
              private["prg_sha256"] == PRIVATE_PRG_SHA256
              and private["chr_sha256"] == PRIVATE_CHR_SHA256)
        check("private:no-ram-battery",
              private["battery"] is False and private["chr_is_ram"] is False
              and private["trainer_bytes"] == 0)
        check("private:contract",
              private["cartridge_contract"]["status"] == "SUPPORTED_MMC1"
              and private["cartridge_contract"]["prg_banks_16k"] == 8
              and private["cartridge_contract"]["chr_banks_8k"] == 16)
        check("private:blocked",
              private["execution_status"] == "BLOCKED_MMC1_MAPPER_NOT_YET_IMPLEMENTED")
        check("private:classification",
              private["classification"] == "PRIVATE_LOCAL_COMPATIBILITY_FIXTURE")

        banner("negative")
        expect_fail("bad-magic", lambda: ingestion.ingest(b"XXXX" + rom_a[4:],
                                                          source_label="neg"),
                    (ingestion.P6IngestionError,))
        expect_fail("truncated", lambda: ingestion.ingest(rom_a[:-1],
                                                          source_label="neg"),
                    (ingestion.P6IngestionError,))
        expect_fail("oversized", lambda: ingestion.ingest(rom_a + b"\x00",
                                                          source_label="neg"),
                    (ingestion.P6IngestionError,))
        expect_fail("zero-prg",
                    lambda: ingestion.ingest(_field_probe(rom_a, prg_banks=0),
                                             source_label="neg"),
                    (ingestion.P6IngestionError,))
        prg_over = ingestion.ingest(_field_probe(rom_a, prg_banks=17),
                                    source_label="neg")
        check("classify:prg-over-range",
              prg_over["phase6"]["status"] == "BLOCKED_UNSUPPORTED_MMC1_VARIANT"
              and "prg_size_out_of_supported_range"
              in prg_over["phase6"]["reasons"])
        chr_over = ingestion.ingest(_field_probe(rom_a, chr_banks=17),
                                    source_label="neg")
        check("classify:chr-over-range",
              chr_over["phase6"]["status"] == "BLOCKED_UNSUPPORTED_MMC1_VARIANT"
              and "chr_size_out_of_supported_range"
              in chr_over["phase6"]["reasons"])
        chr_ram = ingestion.ingest(_field_probe(rom_a, chr_banks=0),
                                   source_label="neg")
        check("classify:chr-ram",
              chr_ram["phase6"]["status"] == "BLOCKED_UNSUPPORTED_MMC1_VARIANT"
              and "chr_ram" in chr_ram["phase6"]["reasons"]
              and "chr_rom_absent" in chr_ram["phase6"]["reasons"]
              and chr_ram["vectors"] is None)
        battery = ingestion.ingest(_field_probe(rom_a, flags6=0x12),
                                   source_label="neg")
        check("classify:battery",
              battery["phase6"]["status"] == "BLOCKED_UNSUPPORTED_MMC1_VARIANT"
              and "battery_or_prg_ram" in battery["phase6"]["reasons"])
        prg_ram = ingestion.ingest(_field_probe(rom_a, flags8=1),
                                   source_label="neg")
        check("classify:prg-ram",
              prg_ram["phase6"]["status"] == "BLOCKED_UNSUPPORTED_MMC1_VARIANT"
              and "prg_ram_declared" in prg_ram["phase6"]["reasons"])
        submapper = ingestion.ingest(
            _field_probe(rom_a, flags7=0x08, flags8=0x10), source_label="neg")
        check("classify:submapper",
              submapper["mapper"] == 1
              and submapper["phase6"]["status"] == "BLOCKED_UNSUPPORTED_MMC1_VARIANT"
              and "submapper_nonzero" in submapper["phase6"]["reasons"])
        four_screen = ingestion.ingest(_field_probe(rom_a, flags6=0x18),
                                       source_label="neg")
        check("classify:four-screen",
              four_screen["phase6"]["status"] == "BLOCKED_UNSUPPORTED_MMC1_VARIANT"
              and "four_screen_nametable_layout"
              in four_screen["phase6"]["reasons"])
        mapper2 = ingestion.ingest(_field_probe(rom_a, flags6=0x20),
                                   source_label="neg")
        check("classify:unsupported-mapper",
              mapper2["mapper"] == 2
              and mapper2["phase6"]["status"] == "BLOCKED_UNSUPPORTED_MAPPER"
              and mapper2["vectors"] is None
              and mapper2["vectors_source"] == "unavailable_unsupported_mapper")
        expect_fail("missing-file",
                    lambda: ingestion.ingest_path(
                        pathlib.Path("scratch") / "does-not-exist.nes",
                        source_label="neg"),
                    (ingestion.P6IngestionError,))
        FINDINGS["negative_checks"] = 16

        banner("regressions")
        regressions = []
        for script in REGRESSIONS:
            record = run_regression(script)
            check(f"regression:{script}:exit", record["returncode"] == 0)
            check(f"regression:{script}:stderr", record["stderr_empty"])
            regressions.append(record)
        FINDINGS["regressions"] = regressions

        banner("evidence_hygiene")
        write_json("ingestion.json", {
            "stage": STAGE,
            "public_fixture": doc_public,
            "public_builder": meta_a,
            "private_fixture": private,
            "unsupported_mapper_probe": mapper2,
        })
        write_json("mmc1_requirements.json", {
            "stage": STAGE,
            "subset": subset,
            "public_classification": doc_public["phase6"],
            "private_classification": private["cartridge_contract"],
        })
        write_json("regressions.json", {"stage": STAGE, "regressions": regressions})
        private_bytes = private_fixture.PRIVATE_ROM.read_bytes()
        for name, data in EVIDENCE_WRITES.items():
            check(f"hygiene:no-public-rom-bytes:{name}", rom_a not in data)
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
    (EVIDENCE_DIR / "p6_01_tests.json").write_text(
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
