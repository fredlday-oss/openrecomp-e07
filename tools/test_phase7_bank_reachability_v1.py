#!/usr/bin/env python3
"""OpenRecomp Phase-7 bank-aware reachability gate (P7-04).

Verifies the bank-aware MMC1 PRG reachability model: physical-bank code
identities, fixed/switchable window tracking through the frozen reference
layout model, statically proven constant bank commits, fail-closed
`UNRESOLVED` expansion for ambiguous writers, explicit non-merging of banks
that share CPU address ranges, and deterministic fail-closed statuses.

On success it emits::

    OPENRECOMP_P7_04=PASS
    OPENRECOMP_PHASE7_BANK_REACHABILITY_V1=PASS tests=<count>
    OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN
    OPENRECOMP_PHASE7_TMMT_PLAYABILITY=NOT_PROVEN

Usage:

    python tools/test_phase7_bank_reachability_v1.py \
        --evidence-dir .openrecomp-phase7/evidence/P7-04
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
import p6_mapper1_prg_reference_v1 as prg_reference  # noqa: E402
import p6_private_fixture_v1 as private_fixture  # noqa: E402
import p7_bank_fixtures_v1 as fixtures  # noqa: E402
import p7_bank_reachability_v1 as model  # noqa: E402

STAGE = "P7-04"
STAGE_MARKER = "OPENRECOMP_P7_04"
FEATURE_MARKER = "OPENRECOMP_PHASE7_BANK_REACHABILITY_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE7_TMMT_PLAYABILITY"

P7_03_RECORD_REL = ".openrecomp-phase7/evidence/P7-03/p7_03_tests.json"
P7_03_GATE = "tools/test_phase7_classification_fixture_v1.py"
P6_PROOF_ROM_SHA256 = (
    "9e10dce532266592f9ccda781bc6d3a7354ab4951bd3db87e4f43d1c45056b70")

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


def summarize(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": record["status"],
        "stop": record["stop"],
        "proven_instructions": record["proven_instructions"],
        "unresolved_instructions": record["unresolved_instructions"],
        "unresolved_limited": record["unresolved_limited"],
        "unresolved_limit": record["unresolved_limit"],
        "code_by_bank": record["code_by_bank"],
        "bank_switches": record["bank_switches"],
        "unresolved_mapper_writes":
            record["unresolved_mapper_writes"][:8],
        "unresolved_mapper_write_count":
            len(record["unresolved_mapper_writes"]),
        "unresolved_decode_sites": record["unresolved_decode_sites"][:8],
        "unresolved_decode_count": len(record["unresolved_decode_sites"]),
        "mode_histogram": record["mode_histogram"],
        "multi_bank_cpu_addresses": record["multi_bank_cpu_addresses"],
        "identity_digest": record["identity_digest"],
        "claim": record["claim"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P7-04 bank-aware reachability gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase7/evidence/P7-04")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES, SCRATCH
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    SCRATCH = CONTROL7 / "scratch" / "P7-04"
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}

    print("=== P7-04 Bank-Aware Reachability Gate ===", flush=True)
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
        check("anchor:decoder-unchanged", len(nes.OPCODES) == 151)
        proof_rom, proof_metadata = fixtures.p6_proof.build_proof()
        check("anchor:p6-public-proof-identity",
              proof_metadata["rom_sha256"] == P6_PROOF_ROM_SHA256)

        banner("control_plane")
        state = (CONTROL7 / "STATE.md").read_text(encoding="utf-8")
        queue = (CONTROL7 / "STAGE_QUEUE.md").read_text(encoding="utf-8")
        check("control-plane:stage-row", "| P7-04 |" in queue)
        check("control-plane:terminal-reserved",
              f"{TERMINAL_MARKER}=NOT_PROVEN" in queue
              and f"{TERMINAL_MARKER}=NOT_PROVEN" in state)
        check("control-plane:compat-reserved",
              f"{COMPAT_MARKER}=NOT_PROVEN" in queue
              and f"{COMPAT_MARKER}=NOT_PROVEN" in state)
        check("control-plane:playability-reserved",
              f"{PLAYABILITY_MARKER}=NOT_PROVEN" in queue
              and f"{PLAYABILITY_MARKER}=NOT_PROVEN" in state)

        banner("layout_model")
        controls = (0x00, 0x04, 0x08, 0x0A, 0x0C, 0x0E, 0x0F, 0x1F)
        prg_values = (0, 1, 2, 3, 5, 7)
        checked = 0
        for bank_count in (1, 2, 4, 8, 16):
            for control in controls:
                for prg_reg in prg_values:
                    expected = prg_reference.reference_window_banks(
                        control, prg_reg, bank_count)
                    partial = model.window_banks_partial(
                        control, prg_reg, bank_count)
                    check(
                        f"layout:mode-banks-{bank_count}-{control:02x}-{prg_reg}",
                        partial == expected)
                    checked += 1
        check("layout:partial-unknown-control",
              model.window_banks_partial(None, 3, 4) == (None, None))
        check("layout:partial-mode3-fixed-high",
              model.window_banks_partial(0x0C, None, 4) == (None, 3))
        check("layout:partial-mode2-fixed-low",
              model.window_banks_partial(0x08, None, 4) == (0, None))
        FINDINGS["layout_combinations"] = checked

        banner("proven_bank_case")
        proven = fixtures.proven_fixture()
        record = model.analyze(proven["prg"], proven["prg_banks"],
                               proven["roots"])
        record_repeat = model.analyze(proven["prg"], proven["prg_banks"],
                                      proven["roots"])
        check("proven:deterministic",
              canonical_text(record) == canonical_text(record_repeat))
        check("proven:status", record["status"] == "OK"
              and record["unresolved_instructions"] == 0)
        target = proven["expected_bank"]
        banks_found = {entry["bank"]: entry for entry in record["code_by_bank"]}
        check("proven:target-bank-only",
              sorted(banks_found) == sorted([target, proven["prg_banks"] - 1])
              and banks_found[target]["provenance"] == "PROVEN"
              and banks_found[target]["proven_instructions"] == 3
              and banks_found[target]["address_samples"][0] == 0x8000)
        for other in range(proven["prg_banks"] - 1):
            if other != target:
                check(f"proven:bank-{other}-unreached", other not in banks_found)
        switch = record["bank_switches"]
        check("proven:switch-recorded",
              len(switch) == 1 and switch[0]["register"] == 3
              and switch[0]["value"] == target
              and switch[0]["window_8000_bank"] == target
              and switch[0]["window_c000_bank"] == proven["prg_banks"] - 1
              and switch[0]["result_layout"]["prg_mode"] == 3)
        check("proven:no-merge",
              record["multi_bank_cpu_addresses"] == {})
        FINDINGS["proven"] = summarize(record)

        banner("reset_bit_case")
        reset_bit = fixtures.reset_bit_fixture()
        rb = model.analyze(reset_bit["prg"], reset_bit["prg_banks"],
                           reset_bit["roots"])
        rb_banks = {entry["bank"]: entry for entry in rb["code_by_bank"]}
        check("reset-bit:proven-target",
              rb["status"] == "OK"
              and rb_banks[reset_bit["expected_bank"]]["provenance"] == "PROVEN"
              and rb["bank_switches"][0]["value"]
              == reset_bit["expected_bank"])
        FINDINGS["reset_bit"] = summarize(rb)

        banner("unknown_value_case")
        unknown = fixtures.unknown_fixture()
        uk = model.analyze(unknown["prg"], unknown["prg_banks"],
                           unknown["roots"])
        check("unknown:status", uk["status"] == "OK")
        check("unknown:expanded",
              uk["unresolved_limited"] is True
              and uk["proven_instructions"] == 16
              and uk["unresolved_instructions"] == uk["unresolved_limit"] - 7)
        uk_banks = {entry["bank"]: entry for entry in uk["code_by_bank"]}
        check("unknown:all-banks-candidates",
              sorted(uk_banks) == list(range(unknown["prg_banks"]))
              and all(entry["provenance"] == "UNRESOLVED"
                      for entry in uk_banks.values())
              and all(uk_banks[bank]["proven_instructions"] == 0
                      for bank in range(unknown["prg_banks"] - 1))
              and uk_banks[unknown["prg_banks"] - 1]["proven_instructions"]
              == 16)
        for bank in range(unknown["prg_banks"]):
            check(f"unknown:bank-{bank}-routine-candidate",
                  0x8000 in uk_banks[bank]["address_samples"])
        check("unknown:no-merge",
              uk["multi_bank_cpu_addresses"].get("32768")
              == list(range(unknown["prg_banks"])))
        check("unknown:writers-recorded",
              len(uk["unresolved_mapper_writes"]) > 0)
        FINDINGS["unknown"] = summarize(uk)

        banner("suppression_case")
        suppression = fixtures.suppression_fixture()
        sp = model.analyze(suppression["prg"], suppression["prg_banks"],
                           suppression["roots"])
        check("suppression:status-ok", sp["status"] == "OK")
        check("suppression:ambiguous-write",
              any("consecutive" in entry["reason"]
                  for entry in sp["unresolved_mapper_writes"]))
        check("suppression:expanded", sp["unresolved_limited"] is True)
        FINDINGS["suppression"] = summarize(sp)

        banner("span_case")
        span = fixtures.span_fixture()
        sp_span = model.analyze(span["prg"], span["prg_banks"], span["roots"])
        check("span:fail-closed",
              sp_span["status"] == "BLOCKED_WINDOW_SPAN"
              and sp_span["stop"]["address"] == 0xBFFF
              and sp_span["stop"]["bank"] == 1)
        FINDINGS["span"] = summarize(sp_span)

        banner("p6_public_case")
        public = fixtures.p6_public_proof()
        pb = model.analyze(public["prg"], public["prg_banks"], public["roots"])
        check("p6-public:status",
              pb["status"] == "OK"
              and pb["proven_instructions"] > 0
              and pb["unresolved_limited"] is True)
        fixed_bank = public["prg_banks"] - 1
        pb_banks = {entry["bank"]: entry for entry in pb["code_by_bank"]}
        check("p6-public:fixed-window-proven",
              fixed_bank in pb_banks
              and pb_banks[fixed_bank]["proven_instructions"] > 0)
        proven_entries = [entry for entry in pb["code_by_bank"]
                          if entry["proven_instructions"] > 0]
        check("p6-public:proven-in-fixed-window",
              [entry["bank"] for entry in proven_entries] == [fixed_bank])
        check("p6-public:ambiguous-writers-recorded",
              len(pb["unresolved_mapper_writes"]) > 0)
        FINDINGS["p6_public"] = summarize(pb)

        banner("fail_closed")
        cases = (
            ("bad-bank-count", lambda: model.analyze(
                proven["prg"], 3, proven["roots"])),
            ("bad-prg-size", lambda: model.analyze(
                proven["prg"][:-1], proven["prg_banks"], proven["roots"])),
            ("bad-root", lambda: model.analyze(
                proven["prg"], proven["prg_banks"], [0x100])),
            ("bad-budget", lambda: model.analyze(
                proven["prg"], proven["prg_banks"], proven["roots"],
                budget=0)),
            ("bad-unresolved-limit", lambda: model.analyze(
                proven["prg"], proven["prg_banks"], proven["roots"],
                unresolved_limit=0)),
        )
        for label, thunk in cases:
            try:
                thunk()
            except model.BankReachabilityError:
                check(f"negative:{label}", True)
            else:
                raise AssertionError(f"negative:{label}")
        tiny = model.analyze(proven["prg"], proven["prg_banks"],
                             proven["roots"], budget=5)
        check("negative:tiny-budget-fails-closed",
              tiny["status"] == "BLOCKED_BUDGET")

        banner("regressions")
        regressions = []
        for script in REGRESSIONS:
            regression_record = run_regression(script)
            check(f"regression:{script}:exit",
                  regression_record["returncode"] == 0)
            check(f"regression:{script}:stderr",
                  regression_record["stderr_empty"])
            regressions.append(regression_record)
        p7_03_regression = run_regression(
            P7_03_GATE, ["--evidence-dir",
                         ".openrecomp-phase7/scratch/P7-04/regression_p7_03"])
        check("regression:p7-03:exit", p7_03_regression["returncode"] == 0)
        check("regression:p7-03:stderr", p7_03_regression["stderr_empty"])
        check("regression:p7-03:marker",
              any(marker == "OPENRECOMP_P7_03=PASS"
                  for marker in p7_03_regression["markers"]))
        regressions.append(p7_03_regression)
        FINDINGS["regressions"] = regressions

        banner("evidence")
        write_json("bank_reachability.json", {
            "stage": STAGE,
            "model": "p7_bank_reachability_v1",
            "layout_combinations": checked,
            "proven": summarize(record),
            "reset_bit": summarize(rb),
            "unknown_values": summarize(uk),
            "suppression": summarize(sp),
            "window_span": summarize(sp_span),
            "p6_public": summarize(pb),
            "tiny_budget": summarize(tiny),
            "fixtures": {
                "proven_prg_sha256": sha256_bytes(proven["prg"]),
                "unknown_prg_sha256": sha256_bytes(unknown["prg"]),
                "reset_bit_prg_sha256": sha256_bytes(reset_bit["prg"]),
                "suppression_prg_sha256": sha256_bytes(suppression["prg"]),
                "span_prg_sha256": sha256_bytes(span["prg"]),
                "p6_public_rom_sha256": proof_metadata["rom_sha256"],
            },
            "non_merging_claim":
                "code identity is (physical bank, cpu address); the same CPU "
                "address under different banks is reported in "
                "multi_bank_cpu_addresses and never merged",
            "public_claim": "bounded bank-aware MMC1 reachability model for "
                            "the audited public fixtures and the synthetic "
                            "original Phase-7 fixtures only",
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
    (EVIDENCE_DIR / "p7_04_tests.json").write_text(
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
