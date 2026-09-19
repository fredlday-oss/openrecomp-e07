#!/usr/bin/env python3
"""OpenRecomp Phase-7 evidence-driven translation closure gate (P7-12).

Verifies the inline-dispatch closure required by the P7-11 evidence: the
classified data table is skipped, the proven finite target set is followed and
the frontier resumes after the table, on both the public P7-03 fixture (whose
runtime evidence proves the mechanism) and the private power-on image. All
other undocumented bytes, indirect jumps and budgets still fail closed.

On success it emits::

    OPENRECOMP_P7_12=PASS
    OPENRECOMP_PHASE7_TRANSLATION_CLOSURE_V1=PASS tests=<count>
    OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN
    OPENRECOMP_PHASE7_TMMT_PLAYABILITY=NOT_PROVEN

Usage:

    python tools/test_phase7_translation_closure_v1.py \
        --evidence-dir .openrecomp-phase7/evidence/P7-12
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
import p7_classification_fixture_v1 as classification_fixture  # noqa: E402
import p7_inline_closure_v1 as closure  # noqa: E402
import p7_opcode_7c_v1 as opcode_module  # noqa: E402

STAGE = "P7-12"
STAGE_MARKER = "OPENRECOMP_P7_12"
FEATURE_MARKER = "OPENRECOMP_PHASE7_TRANSLATION_CLOSURE_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE7_TMMT_PLAYABILITY"

P7_11_RECORD_REL = ".openrecomp-phase7/evidence/P7-11/p7_11_tests.json"
P7_11_GATE = "tools/test_phase7_private_frontier_v1.py"
P7_03_RECORD_REL = ".openrecomp-phase7/evidence/P7-03/p7_03_tests.json"

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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P7-12 translation closure gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase7/evidence/P7-12")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES, SCRATCH
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    SCRATCH = CONTROL7 / "scratch" / "P7-12"
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}

    print("=== P7-12 Translation Closure Gate ===", flush=True)
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
        check("anchor:p7-03-record-pass",
              read_json(ROOT / P7_03_RECORD_REL)["status"] == "PASS")
        check("anchor:p7-11-record-pass",
              read_json(ROOT / P7_11_RECORD_REL)["status"] == "PASS")
        check("anchor:decoder-unchanged", len(nes.OPCODES) == 151)

        banner("control_plane")
        state = (CONTROL7 / "STATE.md").read_text(encoding="utf-8")
        queue = (CONTROL7 / "STAGE_QUEUE.md").read_text(encoding="utf-8")
        check("control-plane:stage-row", "| P7-12 |" in queue)
        check("control-plane:terminal-reserved",
              f"{TERMINAL_MARKER}=NOT_PROVEN" in queue
              and f"{TERMINAL_MARKER}=NOT_PROVEN" in state)
        check("control-plane:compat-reserved",
              f"{COMPAT_MARKER}=NOT_PROVEN" in queue
              and f"{COMPAT_MARKER}=NOT_PROVEN" in state)
        check("control-plane:playability-reserved",
              f"{PLAYABILITY_MARKER}=NOT_PROVEN" in queue
              and f"{PLAYABILITY_MARKER}=NOT_PROVEN" in state)

        banner("public_fixture_closure")
        rom, metadata = classification_fixture.build()
        inventory = classification_fixture.inventory(rom)
        image = classification_fixture.cpu_image(rom, inventory)
        roots = [inventory["vectors"][name]
                 for name in ("reset", "nmi", "irq")]
        report = closure.analyze(image, roots)
        report_repeat = closure.analyze(image, roots)
        check("public:deterministic",
              canonical_text(report) == canonical_text(report_repeat))
        check("public:one-table",
              len(report["tables"]) == 1)
        table = report["tables"][0]
        mechanism = metadata["mechanism"]
        check("public:table-structure",
              table["call_site"] == mechanism["call_site"]
              and table["callee"] == mechanism["dispatch_entry"]
              and table["table_base"] == mechanism["table_base"]
              and table["entries"] == 3
              and tuple(table["targets"]) == tuple(mechanism["targets"])
              and table["resume_address"] == mechanism["resume_code"])
        check("public:closure-follows-targets",
              report["closure"]["resolved_site_count"] == 1
              and report["closure"]["instructions"] > 30
              and report["delta_instructions"] > 0
              and report["closure"]["stop"] is None)
        check("public:targets-reached",
              report["closure"]["addresses"] is not None
              and all(target in report["closure"]["addresses"]
                      for target in mechanism["targets"])
              and table["resume_address"]
              == table["table_base"] + table["byte_length"])
        FINDINGS["public"] = {
            "table": table,
            "baseline_instructions": report["baseline"]["instructions"],
            "closure_instructions": report["closure"]["instructions"],
            "delta_instructions": report["delta_instructions"],
        }

        banner("private_closure")
        data = private_fixture.PRIVATE_ROM.read_bytes()
        private_image, private_inventory = opcode_module.build_image(data)
        private_roots = [private_inventory["vectors"][name]
                         for name in ("reset", "nmi", "irq")]
        private_report = closure.analyze(private_image, private_roots)
        check("private:one-table",
              len(private_report["tables"]) == 1)
        private_table = private_report["tables"][0]
        check("private:table-structure",
              private_table["call_site"] == 0xC56D
              and private_table["callee"] == 0xC71F
              and private_table["table_base"] == 0xC570
              and private_table["entries"] == 6
              and private_table["resume_address"] == 0xC57C)
        check("private:frontier-advances",
              private_report["closure"]["instructions"] == 1255
              and private_report["baseline"]["instructions"] == 1250
              and private_report["delta_instructions"] == 5
              and private_report["closure"]["stop"]["address"] == 0xBB6B
              and private_report["closure"]["stop"]["kind"]
              == "undocumented_opcode")
        check("private:no-rom-bytes",
              private_fixture.PRIVATE_ROM.read_bytes()
              not in canonical_text(private_report).encode("utf-8"))
        FINDINGS["private"] = {
            "table": private_table,
            "baseline_instructions": private_report["baseline"]["instructions"],
            "closure_instructions":
                private_report["closure"]["instructions"],
            "delta_instructions": private_report["delta_instructions"],
            "stop": private_report["closure"]["stop"],
        }

        banner("fail_closed")
        synthetic = bytearray(0x10000)
        synthetic[0xC000:0xC003] = bytes([0x20, 0x10, 0xC0])  # jsr $C010
        synthetic[0xC003:0xC005] = bytes([0x7C, 0xC1])        # table-like data
        synthetic[0xC010] = 0x60                              # rts callee
        baseline = opcode_module.candidate_walk(bytes(synthetic), [0xC000])
        check("negative:non-consuming-callee-no-table",
              closure.detect_inline_tables(bytes(synthetic), baseline) == [])
        synthetic2 = bytearray(0x10000)
        synthetic2[0xC000:0xC003] = bytes([0x20, 0x10, 0xC0])
        synthetic2[0xC003] = 0x7C
        synthetic2[0xC010:0xC01B] = bytes(
            [0x68, 0x85, 0x00, 0x68, 0x85, 0x01, 0xB1, 0x00, 0x6C, 0x02,
             0x00])
        baseline2 = opcode_module.candidate_walk(bytes(synthetic2), [0xC000])
        check("negative:empty-table-no-closure",
              closure.detect_inline_tables(bytes(synthetic2), baseline2) == [])
        synthetic3 = bytearray(0x10000)
        synthetic3[0xC000:0xC010] = bytes([0xEA] * 16)
        tiny = closure.closure_walk(bytes(synthetic3), [0xC000], [], budget=3)
        check("negative:budget-fail-closed",
              tiny["stop"]["kind"] == "budget"
              and tiny["instructions"] == 3)

        banner("regressions")
        regressions = []
        for script in REGRESSIONS:
            regression_record = run_regression(script)
            check(f"regression:{script}:exit",
                  regression_record["returncode"] == 0)
            check(f"regression:{script}:stderr",
                  regression_record["stderr_empty"])
            regressions.append(regression_record)
        p7_11_regression = run_regression(
            P7_11_GATE, ["--evidence-dir",
                         ".openrecomp-phase7/scratch/P7-12/regression_p7_11"])
        check("regression:p7-11:exit", p7_11_regression["returncode"] == 0)
        check("regression:p7-11:stderr", p7_11_regression["stderr_empty"])
        check("regression:p7-11:marker",
              any(marker == "OPENRECOMP_P7_11=PASS"
                  for marker in p7_11_regression["markers"]))
        regressions.append(p7_11_regression)
        FINDINGS["regressions"] = regressions

        banner("evidence")
        write_json("inline_closure.json", {
            "stage": STAGE,
            "mechanism": {
                "definition": "jsr whose fallthrough is undocumented, whose "
                              "callee consumes the pushed return address and "
                              "whose fallthrough decodes as an in-window "
                              "little-endian pointer table",
                "closure_rule": "skip the classified table bytes, follow the "
                                "callee and the proven finite target set, "
                                "resume after the table",
                "fail_closed": "undocumented bytes, unresolved indirect "
                               "jumps and budgets still stop the walk",
            },
            "public_fixture": FINDINGS["public"],
            "private_image": FINDINGS["private"],
            "claim": "the added control-flow behaviour is exactly the "
                     "evidence-required inline-dispatch closure and is proven "
                     "on the public fixture before private application",
            "public_claim": metadata["public_claim"],
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
    (EVIDENCE_DIR / "p7_12_tests.json").write_text(
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
