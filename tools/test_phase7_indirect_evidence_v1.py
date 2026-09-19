#!/usr/bin/env python3
"""OpenRecomp Phase-7 indirect-jump evidence gate (P7-06).

Verifies the deterministic indirect-jump evidence model on the three private
`$E2` sites (`0x86E8`, `0x8956`, `0x8F3C`) and on original synthetic public
images covering `RESOLVED_EXACT`, `RESOLVED_FINITE_SET`, `UNRESOLVED` and
`IMPOSSIBLE`. Targets are enumerated from proven value sources only and are
never guessed; no ROM bytes are recorded.

On success it emits::

    OPENRECOMP_P7_06=PASS
    OPENRECOMP_PHASE7_INDIRECT_MODEL_V1=PASS tests=<count>
    OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN
    OPENRECOMP_PHASE7_TMMT_PLAYABILITY=NOT_PROVEN

Usage:

    python tools/test_phase7_indirect_evidence_v1.py \
        --evidence-dir .openrecomp-phase7/evidence/P7-06
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTROL7 = ROOT / ".openrecomp-phase7"
for entry in (str(ROOT), str(ROOT / "tools"),
              str(ROOT / ".openrecomp-phase5" / "src"),
              str(ROOT / ".openrecomp-phase6" / "src"),
              str(CONTROL7 / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import adapters.nes6502 as nes  # noqa: E402
import p6_private_fixture_v1 as private_fixture  # noqa: E402
import p7_indirect_evidence_v1 as evidence  # noqa: E402

STAGE = "P7-06"
STAGE_MARKER = "OPENRECOMP_P7_06"
FEATURE_MARKER = "OPENRECOMP_PHASE7_INDIRECT_MODEL_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE7_TMMT_PLAYABILITY"

P7_05_RECORD_REL = ".openrecomp-phase7/evidence/P7-05/p7_05_tests.json"
P7_05_GATE = "tools/test_phase7_bank_structure_v1.py"
P7_01_RECORD_REL = ".openrecomp-phase7/evidence/P7-01/p7_01_tests.json"

EXPECTED_SITES = {
    0x86E8: {
        "classification": "RESOLVED_FINITE_SET",
        "bank_state": "PROVEN",
        "evaluated_banks": [0],
        "domain": [0, 2, 4, 6],
        "table_base": 0x8FB8,
        "targets": [(0, 34555), (0, 34717), (0, 34737), (0, 34818)],
        "infeasible": 0,
    },
    0x8956: {
        "classification": "RESOLVED_FINITE_SET",
        "bank_state": "UNRESOLVED",
        "evaluated_banks": [0],
        "domain": [0, 2, 4, 6],
        "table_base": 0x8FCC,
        "targets": [(0, 36099), (0, 36138), (0, 36216), (0, 36462)],
        "infeasible": 0,
    },
    0x8F3C: {
        "classification": "RESOLVED_FINITE_SET",
        "bank_state": "MODEL_UNREACHED",
        "evaluated_banks": [0, 1, 2, 3, 4, 5, 6, 7],
        "domain_size": 128,
        "table_base": 0x8FC0,
        "feasible": 300,
        "infeasible": 442,
    },
}

REGRESSIONS = ("tools/test_nes_rom_v1.py",)

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


def canonical(document: Any) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True)
            + "\n").encode("utf-8")


def canonical_text(document: Any) -> str:
    return json.dumps(document, sort_keys=True, separators=(",", ":"))


def write_json(name: str, document: Any) -> None:
    EVIDENCE_WRITES[name] = canonical(document)


def read_json(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def run_regression(script: str, extra: list[str] | None = None) -> dict[str, Any]:
    completed = subprocess.run([sys.executable, script, *(extra or [])],
                               cwd=str(ROOT), capture_output=True)
    stdout = completed.stdout
    stderr = completed.stderr
    markers = [line for line in stdout.decode("utf-8", errors="replace").splitlines()
               if line.startswith("OPENRECOMP_")]
    return {
        "script": script,
        "command": ["python", script, *(extra or [])],
        "returncode": completed.returncode,
        "stdout_bytes": len(stdout),
        "stdout_sha256_raw": sha256_bytes(stdout),
        "stdout_sha256_lf": sha256_bytes(stdout.replace(b"\r\n", b"\n")),
        "stderr_bytes": len(stderr),
        "stderr_empty": not stderr,
        "markers": markers,
    }


def synthetic(segments: dict[int, bytes]) -> bytes:
    image = bytearray(0x10000)
    for address, payload in segments.items():
        image[address:address + len(payload)] = payload
    return bytes(image)


def classify_synthetic(image: bytes, site: int) -> dict[str, Any]:
    prg = image[0x8000:0x10000]
    return evidence.analyze_image(image, prg, 1, [site], roots=[0xC000])


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P7-06 indirect-jump evidence gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase7/evidence/P7-06")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES, SCRATCH
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    SCRATCH = CONTROL7 / "scratch" / "P7-06"
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}

    print("=== P7-06 Indirect Jump Evidence Gate ===", flush=True)
    failure: str | None = None
    try:
        banner("source_integrity")
        manifest = CONTROL7 / "SOURCE_SHA256SUMS.txt"
        entries = []
        for line in manifest.read_text(encoding="utf-8").strip().splitlines():
            digest, rel = line.split(" *", 1)
            entries.append((digest, rel))
        bad = [rel for digest, rel in entries
               if not (ROOT / rel).is_file() or sha256_file(ROOT / rel) != digest]
        check("source:manifest-verified", bool(entries) and not bad)

        banner("anchors")
        check("anchor:p7-01-record-pass",
              read_json(ROOT / P7_01_RECORD_REL)["status"] == "PASS")
        check("anchor:p7-05-record-pass",
              read_json(ROOT / P7_05_RECORD_REL)["status"] == "PASS")
        check("anchor:decoder-unchanged", len(nes.OPCODES) == 151)

        banner("control_plane")
        state = (CONTROL7 / "STATE.md").read_text(encoding="utf-8")
        queue = (CONTROL7 / "STAGE_QUEUE.md").read_text(encoding="utf-8")
        check("control-plane:stage-row", "| P7-06 |" in queue)
        check("control-plane:terminal-reserved",
              f"{TERMINAL_MARKER}=NOT_PROVEN" in queue
              and f"{TERMINAL_MARKER}=NOT_PROVEN" in state)
        check("control-plane:compat-reserved",
              f"{COMPAT_MARKER}=NOT_PROVEN" in queue
              and f"{COMPAT_MARKER}=NOT_PROVEN" in state)
        check("control-plane:playability-reserved",
              f"{PLAYABILITY_MARKER}=NOT_PROVEN" in queue
              and f"{PLAYABILITY_MARKER}=NOT_PROVEN" in state)

        banner("private_sites")
        report = evidence.analyze_private()
        report_repeat = evidence.analyze_private()
        check("private:deterministic",
              canonical_text(report) == canonical_text(report_repeat))
        check("private:image-identity",
              report["image_sha256"]
              == "2a9345e608ec0c57470dc6658ce8199ddea9c18076134d9ef2a56f91b0a066d1")
        check("private:three-finite-sets",
              report["counts"] == {"RESOLVED_FINITE_SET": 3})
        by_site = {record["site"]: record for record in report["sites"]}
        check("private:site-addresses",
              sorted(by_site) == sorted(EXPECTED_SITES))
        for site, expected in EXPECTED_SITES.items():
            record = by_site[site]
            check(f"private:{site:#06x}:pointer",
                  record["pointer"] == 0xE2 and record["window"] == "low")
            check(f"private:{site:#06x}:classification",
                  record["classification"] == expected["classification"]
                  and record["state"] == expected["classification"])
            check(f"private:{site:#06x}:chain",
                  record["chain_unique"] is True
                  and record["chain_relevant_length"] > 0
                  and record["definitions"]["0xe2"]["source"]["kind"]
                  == "table"
                  and record["definitions"]["0xe3"]["source"]["kind"]
                  == "table")
            bank = record["bank_provenance"]
            check(f"private:{site:#06x}:bank-provenance",
                  bank["state"] == expected["bank_state"]
                  and record["evaluated_banks"] == expected["evaluated_banks"])
            check(f"private:{site:#06x}:table",
                  record["table_base"] == expected["table_base"]
                  and record["table_high"] == expected["table_base"] + 1)
            if "domain" in expected:
                check(f"private:{site:#06x}:domain",
                      record["index_domain"] == expected["domain"]
                      and record["index_domain_size"] == len(expected["domain"]))
            else:
                check(f"private:{site:#06x}:domain",
                      record["index_domain_size"] == expected["domain_size"])
                check(f"private:{site:#06x}:feasible-count",
                      len(record["feasible_targets"]) == expected["feasible"])
            if "targets" in expected:
                check(f"private:{site:#06x}:targets",
                      [tuple(item) for item in record["feasible_targets"]]
                      == expected["targets"])
            check(f"private:{site:#06x}:infeasible",
                  record["infeasible_count"] == expected["infeasible"])
        check("private:bank-model",
              report["bank_model"]["status"] == "BLOCKED_UNDECODABLE"
              and report["bank_model"]["proven_instructions"] == 530)
        check("private:no-rom-bytes",
              private_fixture.PRIVATE_ROM.read_bytes()
              not in canonical_text(report).encode("utf-8"))
        FINDINGS["private_counts"] = report["counts"]
        FINDINGS["private_site_digest"] = sha256_bytes(
            canonical_text(report).encode("utf-8"))

        banner("unit_states")
        exact = classify_synthetic(synthetic({
            0xC000: bytes([0xA9, 0x00, 0x85, 0xE2, 0xA9, 0xC1, 0x85, 0xE3,
                           0x6C, 0xE2, 0x00]),
            0xC100: bytes([0x60]),
        }), 0xC008)
        check("unit:resolved-exact",
              exact["sites"][0]["classification"] == "RESOLVED_EXACT"
              and exact["sites"][0]["feasible_targets"] == [[0, 0xC100]])
        finite = classify_synthetic(synthetic({
            0x8000: bytes([0x00, 0xC1, 0x10, 0xC1, 0x20, 0xC1, 0x30, 0xC1]),
            0xC000: bytes([0xA5, 0x10, 0x29, 0x06, 0xA8, 0xB9, 0x00, 0x80,
                           0x85, 0xE2, 0xB9, 0x01, 0x80, 0x85, 0xE3,
                           0x6C, 0xE2, 0x00]),
            0xC100: bytes([0x60]), 0xC110: bytes([0x60]),
            0xC120: bytes([0x60]), 0xC130: bytes([0x60]),
        }), 0xC00F)
        check("unit:resolved-finite-set",
              finite["sites"][0]["classification"] == "RESOLVED_FINITE_SET"
              and finite["sites"][0]["index_domain"] == [0, 2, 4, 6]
              and [tuple(item) for item in
                   finite["sites"][0]["feasible_targets"]]
              == [(0, 0xC100), (0, 0xC110), (0, 0xC120), (0, 0xC130)])
        unresolved = classify_synthetic(synthetic({
            0xC000: bytes([0xA5, 0x10, 0x85, 0xE2, 0xA5, 0x10, 0x85, 0xE3,
                           0x6C, 0xE2, 0x00]),
        }), 0xC008)
        check("unit:unresolved",
              unresolved["sites"][0]["classification"] == "UNRESOLVED"
              and "not statically known" in unresolved["sites"][0]["reason"])
        impossible = classify_synthetic(synthetic({
            0xC000: bytes([0xA9, 0x34, 0x85, 0xE2, 0xA9, 0x12, 0x85, 0xE3,
                           0x6C, 0xE2, 0x00]),
        }), 0xC008)
        check("unit:impossible",
              impossible["sites"][0]["classification"] == "IMPOSSIBLE"
              and impossible["sites"][0]["feasible_targets"] == [])
        FINDINGS["unit_states"] = {
            "exact": exact["sites"][0]["classification"],
            "finite": finite["sites"][0]["classification"],
            "unresolved": unresolved["sites"][0]["classification"],
            "impossible": impossible["sites"][0]["classification"],
        }

        banner("fail_closed")
        try:
            evidence.analyze_image(b"\x00" * 10, b"\x00" * 0x4000, 1,
                                   [0xC000], roots=[0xC000])
        except evidence.P7IndirectError:
            check("negative:short-image-rejected", True)
        else:
            raise AssertionError("negative:short-image-rejected")
        try:
            evidence.analyze_private(
                pathlib.Path(r"D:\OpenRecomp\Roms\phase1\nes\primary\absent.nes"))
        except evidence.P7IndirectError:
            check("negative:missing-private-path", True)
        else:
            raise AssertionError("negative:missing-private-path")

        banner("regressions")
        regressions = []
        for script in REGRESSIONS:
            record = run_regression(script)
            check(f"regression:{script}:exit", record["returncode"] == 0)
            check(f"regression:{script}:stderr", record["stderr_empty"])
            regressions.append(record)
        p7_05_regression = run_regression(
            P7_05_GATE, ["--evidence-dir",
                         ".openrecomp-phase7/scratch/P7-06/regression_p7_05"])
        check("regression:p7-05:exit", p7_05_regression["returncode"] == 0)
        check("regression:p7-05:stderr", p7_05_regression["stderr_empty"])
        check("regression:p7-05:marker",
              any(marker == "OPENRECOMP_P7_05=PASS"
                  for marker in p7_05_regression["markers"]))
        regressions.append(p7_05_regression)
        FINDINGS["regressions"] = regressions

        banner("evidence")
        write_json("indirect_evidence.json", {
            "stage": STAGE,
            "fixture": "private_tmnt",
            "image_sha256": report["image_sha256"],
            "image_size": report["image_size"],
            "prg_banks": report["prg_banks"],
            "bank_model": report["bank_model"],
            "counts": report["counts"],
            "sites": report["sites"],
            "unit_states": FINDINGS["unit_states"],
            "claim": report["claim"],
            "public_claim": report["public_claim"],
        })
        private_bytes = private_fixture.PRIVATE_ROM.read_bytes()
        for name, data in EVIDENCE_WRITES.items():
            check(f"hygiene:no-private-rom-bytes:{name}", private_bytes not in data)
        check("hygiene:no-rom-extension-in-scratch",
              not any(path.suffix.lower() in (".nes", ".fds", ".unf", ".unif")
                      for path in SCRATCH.rglob("*") if path.is_file()))
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
            "playability": f"{PLAYABILITY_MARKER}=NOT_PROVEN",
        },
        "checks": sorted(RESULTS, key=lambda item: item["check"]),
        "findings": FINDINGS,
        "failure": failure,
    }
    for name, data in EVIDENCE_WRITES.items():
        (EVIDENCE_DIR / name).write_bytes(data)
    (EVIDENCE_DIR / "p7_06_tests.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        newline="\n")

    print("\n=== RESULT ===")
    print(f"{STAGE_MARKER}={status}")
    print(f"{FEATURE_MARKER}={status} tests={passed}")
    print(f"{TERMINAL_MARKER}=NOT_PROVEN")
    print(f"{COMPAT_MARKER}=NOT_PROVEN")
    print(f"{PLAYABILITY_MARKER}=NOT_PROVEN")
    if failure:
        print(f"FAILURE={failure}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
