#!/usr/bin/env python3
"""OpenRecomp Phase-5 NES/iNES ingestion and inventory gate (P5-01).

Verifies fail-closed iNES/NES 2.0 ingestion and the complete cartridge
inventory for the selected fixtures:

* the original Apache-2.0 public fixture builds deterministically, every
  assembled instruction cross-checks against the frozen NES6502 decoder, and
  the frozen Phase-1 ingestion/NROM mapper accepts it;
* the private local compatibility fixture is inventoried by metadata/hash only
  (never copied) and its unsupported mapper fails closed;
* malformed, truncated, oversized, extended-size and unsupported-mapper
  images behave deterministically without tracebacks.

On success it emits::

    OPENRECOMP_P5_01=PASS
    OPENRECOMP_PHASE5_INGESTION_INVENTORY_V1=PASS tests=<count>
    OPENRECOMP_PHASE5_NES_PLATFORM_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE5_GENERAL_NES_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase5_ingestion_v1.py --evidence-dir .openrecomp-phase5/evidence/P5-01
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
PHASE5 = ROOT / ".openrecomp-phase5"
for entry in (str(ROOT / ".openrecomp-phase5" / "src"), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import nes_rom_v1 as frozen_rom  # noqa: E402
import p5_fixture_build_v1 as fixture_build  # noqa: E402
import p5_ines_v1 as ingestion  # noqa: E402

STAGE = "P5-01"
STAGE_MARKER = "OPENRECOMP_P5_01"
FEATURE_MARKER = "OPENRECOMP_PHASE5_INGESTION_INVENTORY_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE5_NES_PLATFORM_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE5_GENERAL_NES_COMPATIBILITY"

PRIVATE_ROM = pathlib.Path(r"D:\OpenRecomp\Roms\phase1\nes\primary\tmnt.nes")

PUBLIC_ROM_SHA256 = "272c94cdc79463cd1020ff14db1892ba56af07e4cfda97f5f1df89dd807772b9"
PUBLIC_ROM_SIZE = 24592
PUBLIC_PRG_SHA256 = "66e01e755ac4f3f7608b01abef2ed08af237755a30bf28f3ec0915046ce11c9c"
PUBLIC_CHR_SHA256 = "3280d50230de2e2205b1d6a9db40a3a41b0b1a4460cda736690ba8c8252f623e"
PUBLIC_VECTORS = {"nmi": 0xC196, "reset": 0xC000, "irq": 0xC1F7}
PUBLIC_INSTRUCTIONS = 231

PRIVATE_ROM_SHA256 = "2a9345e608ec0c57470dc6658ce8199ddea9c18076134d9ef2a56f91b0a066d1"
PRIVATE_ROM_SIZE = 262160
PRIVATE_PRG_SHA256 = "2fbc367a453504f01d7dec9fcc52c59b249fd8633ee8e5de6c7ec04abe0131bc"
PRIVATE_CHR_SHA256 = "f9e354d57423f5d883663ed56801066ce38ab1a64065a735db88d42aee6eac29"
PRIVATE_MAPPER = 1

REGRESSIONS = (
    ("tools/test_nes_rom_v1.py", []),
    ("tools/test_nes_platform_v1.py", []),
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
    parser = argparse.ArgumentParser(description="P5-01 ingestion/inventory gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase5/evidence/P5-01")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}

    print("=== P5-01 NES/iNES Ingestion and Inventory Gate ===", flush=True)
    failure: str | None = None
    try:
        banner("public_fixture_build")
        rom_a, meta_a = fixture_build.build()
        rom_b, meta_b = fixture_build.build()
        check("public:build-byte-identical", rom_a == rom_b)
        check("public:metadata-identical", meta_a == meta_b)
        check("public:rom-size", len(rom_a) == PUBLIC_ROM_SIZE)
        check("public:rom-sha256", meta_a["rom_sha256"] == PUBLIC_ROM_SHA256)
        check("public:prg-sha256", meta_a["prg_sha256"] == PUBLIC_PRG_SHA256)
        check("public:chr-sha256", meta_a["chr_sha256"] == PUBLIC_CHR_SHA256)
        check("public:prg-size", meta_a["prg_size"] == 0x4000)
        check("public:chr-size", meta_a["chr_size"] == 0x2000)
        check("public:mapper", meta_a["mapper"] == 0)
        check("public:mirroring", meta_a["mirroring"] == "horizontal")
        check("public:vectors", meta_a["vectors"] == PUBLIC_VECTORS)
        check("public:instruction-count",
              meta_a["instruction_count"] == PUBLIC_INSTRUCTIONS)
        check("public:instructions-cross-checked",
              meta_a["instructions_cross_checked"] == PUBLIC_INSTRUCTIONS)
        check("public:header",
              meta_a["header_hex"] == "4e45531a010100000000000000000000")
        check("public:original-license",
              meta_a["origin"] == "original" and meta_a["license"] == "Apache-2.0")

        banner("public_ingestion")
        inv_public = ingestion.ingest(rom_a, source_label="public_fixture")
        doc_public = inv_public.to_document()
        check("public:ingest-mapper", doc_public["mapper"] == 0
              and doc_public["mapper_name"] == "nrom")
        check("public:ingest-sizes",
              doc_public["prg_bytes"] == 0x4000 and doc_public["chr_bytes"] == 0x2000)
        check("public:ingest-exact-size",
              doc_public["actual_size"] == doc_public["declared_size"]
              == PUBLIC_ROM_SIZE)
        check("public:ingest-vectors", doc_public["vectors"] == PUBLIC_VECTORS)
        check("public:ingest-status",
              doc_public["execution_status"] == "SUPPORTED_NROM")
        check("public:ingest-container", doc_public["container"] == "ines")
        check("public:ingest-fingerprint-stable",
              inv_public.fingerprint()
              == ingestion.ingest(rom_a, source_label="public_fixture").fingerprint())
        frozen_classification = frozen_rom.classify(rom_a)
        check("public:frozen-classify",
              frozen_classification.mapper == 0
              and frozen_classification.prg_bytes == 0x4000
              and frozen_classification.chr_bytes == 0x2000)
        mapper = frozen_rom.make_mapper(rom_a)
        check("public:frozen-mapper", type(mapper).__name__ == "NromMapper")
        check("public:frozen-mapper-reset",
              (mapper.cpu_read(0xFFFC) | (mapper.cpu_read(0xFFFD) << 8))
              == PUBLIC_VECTORS["reset"])

        with tempfile.TemporaryDirectory(prefix="p5_ines_") as tmp:
            rom_path = pathlib.Path(tmp) / "public_fixture.nes"
            rom_path.write_bytes(rom_a)
            completed = subprocess.run(
                [sys.executable, str(ROOT / "tools" / "nes_rom_v1.py"), str(rom_path)],
                cwd=str(ROOT), capture_output=True)
            stdout = completed.stdout.decode("utf-8", errors="replace")
            check("public:frozen-cli",
                  completed.returncode == 0 and "OPENRECOMP_NES_ROM_V1=PASS" in stdout
                  and "NES_ROM_MAPPER=0" in stdout)

        banner("private_fixture")
        check("private:exists", PRIVATE_ROM.is_file())
        inv_private = ingestion.ingest_path(PRIVATE_ROM, source_label="private_tmnt")
        doc_private = inv_private.to_document()
        check("private:sha256", doc_private["image_sha256"] == PRIVATE_ROM_SHA256)
        check("private:size", doc_private["actual_size"] == PRIVATE_ROM_SIZE)
        check("private:container", doc_private["container"] == "nes2.0")
        check("private:mapper", doc_private["mapper"] == PRIVATE_MAPPER)
        check("private:mirroring", doc_private["mirroring"] == "horizontal")
        check("private:prg-chr",
              doc_private["prg_bytes"] == 0x20000
              and doc_private["chr_bytes"] == 0x20000)
        check("private:hashes",
              doc_private["prg_sha256"] == PRIVATE_PRG_SHA256
              and doc_private["chr_sha256"] == PRIVATE_CHR_SHA256)
        check("private:vectors-unavailable",
              doc_private["vectors"] is None
              and doc_private["vectors_source"] == "unavailable_unsupported_mapper")
        check("private:blocked",
              doc_private["execution_status"] == "BLOCKED_UNSUPPORTED_MAPPER")
        check("private:no-trainer-battery",
              doc_private["trainer_bytes"] == 0 and doc_private["battery"] is False)
        expect_fail("private:frozen-mapper-unsupported",
                    lambda: frozen_rom.make_mapper(PRIVATE_ROM.read_bytes()),
                    (frozen_rom.NESROMError,))

        banner("negative")
        expect_fail("bad-magic", lambda: ingestion.ingest(b"XXXX" + rom_a[4:],
                                                          source_label="neg"),
                    (ingestion.P5IngestionError,))
        expect_fail("truncated",
                    lambda: ingestion.ingest(rom_a[:-1], source_label="neg"),
                    (ingestion.P5IngestionError,))
        expect_fail("oversized",
                    lambda: ingestion.ingest(rom_a + b"\x00", source_label="neg"),
                    (ingestion.P5IngestionError,))
        zero_prg = bytearray(rom_a)
        zero_prg[4] = 0
        expect_fail("zero-prg", lambda: ingestion.ingest(bytes(zero_prg),
                                                         source_label="neg"),
                    (ingestion.P5IngestionError, frozen_rom.NESROMError))
        extended = bytearray(rom_a)
        extended[7] = 0x08  # NES 2.0 signature
        extended[4] = 0x0F  # exponent/extended PRG size form
        extended[8:16] = b"\x00" * 8
        expect_fail("nes2-extended-size",
                    lambda: ingestion.ingest(bytes(extended), source_label="neg"),
                    (ingestion.P5IngestionError,))
        msb = bytearray(rom_a)
        msb[7] = 0x08
        msb[9] = 0x01  # PRG-size MSB declared
        msb[8] = 0x00
        msb[10] = 0x00
        msb[11] = 0x00
        msb[12] = 0x00
        msb[13] = 0x00
        msb[14] = 0x00
        msb[15] = 0x00
        expect_fail("nes2-prg-msb",
                    lambda: ingestion.ingest(bytes(msb), source_label="neg"),
                    (ingestion.P5IngestionError,))
        mapper5 = bytearray(rom_a)
        mapper5[6] = 0x50  # mapper 5 in the low nibble
        mapper5[7] = 0x00
        mapper5_inv = ingestion.ingest(bytes(mapper5), source_label="neg")
        check("unsupported:mapper-classified",
              mapper5_inv.mapper == 5
              and mapper5_inv.execution_status == "BLOCKED_UNSUPPORTED_MAPPER")
        FINDINGS["negative_checks"] = 7

        banner("regressions")
        regressions = []
        for script, extra in REGRESSIONS:
            record = run_regression(script, extra)
            record["marker"] = script
            check(f"regression:{script}:exit", record["returncode"] == 0)
            check(f"regression:{script}:stderr", record["stderr_empty"])
            regressions.append(record)
        FINDINGS["regressions"] = regressions

        banner("evidence_hygiene")
        write_json("ingestion.json", {
            "stage": STAGE,
            "public_fixture": doc_public,
            "public_builder": meta_a,
            "private_fixture": doc_private,
            "unsupported_mapper_probe": mapper5_inv.to_document(),
        })
        write_json("regressions.json", {"stage": STAGE, "regressions": regressions})
        private_bytes = PRIVATE_ROM.read_bytes()
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
    (EVIDENCE_DIR / "p5_01_tests.json").write_text(
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
