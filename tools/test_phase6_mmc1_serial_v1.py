#!/usr/bin/env python3
"""OpenRecomp Phase-6 MMC1 serial register protocol gate (P6-02).

Differentially verifies the audited `MMC1_SUBSET_V1` serial protocol
implementation against an independently structured reference model over
exhaustive bounded and deterministic pseudo-random write plans, and verifies
fail-closed behaviour for malformed writes.

On success it emits::

    OPENRECOMP_P6_02=PASS
    OPENRECOMP_PHASE6_MMC1_SERIAL_V1=PASS tests=<count>
    OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase6_mmc1_serial_v1.py --evidence-dir .openrecomp-phase6/evidence/P6-02
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
import p6_mmc1_serial_reference_v1 as reference_model  # noqa: E402
import p6_mmc1_serial_v1 as serial_model  # noqa: E402
import p6_private_fixture_v1 as private_fixture  # noqa: E402

STAGE = "P6-02"
STAGE_MARKER = "OPENRECOMP_P6_02"
FEATURE_MARKER = "OPENRECOMP_PHASE6_MMC1_SERIAL_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY"

PHASE5_TAG_OBJECT = "b5d6832ba2374b810f4c24500ed9093a9481fd8d"
PHASE5_COMMIT = "e8d3627a622d0ca3196b117c5112f29fabdb49e7"
PHASE5_TREE = "468fb9788350de393d3de2ca9471b7d874ee8dc9"

WINDOWS = (
    (0x8000, "control", 0),
    (0xA000, "chr_bank_0", 1),
    (0xC000, "chr_bank_1", 2),
    (0xE000, "prg_bank", 3),
)

RANDOM_SEED = 0x504602
RANDOM_STEPS = 3000

RESULTS: list[dict[str, str]] = []
FINDINGS: dict[str, Any] = {}
EVIDENCE_WRITES: dict[str, bytes] = {}
COMPARISONS = 0


class LCG:
    """Deterministic 32-bit linear congruential generator (Numerical Recipes)."""

    def __init__(self, seed: int) -> None:
        self.state = seed & 0xFFFFFFFF

    def next(self) -> int:
        self.state = (self.state * 1664525 + 1013904223) & 0xFFFFFFFF
        return self.state


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


def replay(label: str, steps: list[tuple[int, int, int]]):
    """Run one write plan through both models, requiring exact agreement."""
    global COMPARISONS
    implementation = serial_model.MMC1Serial()
    reference = reference_model.MMC1SerialReference()
    actions = []
    for step in steps:
        produced = implementation.write(*step)
        expected = reference.write(*step)
        for field in ("action", "register", "register_value"):
            if produced.get(field) != expected.get(field):
                raise AssertionError(
                    f"vector {label}: {field} mismatch at {step}: "
                    f"{produced} vs {expected}")
        if implementation.state() != reference.snapshot():
            raise AssertionError(
                f"vector {label}: state mismatch at {step}: "
                f"{implementation.state()} vs {reference.snapshot()}")
        actions.append(produced)
        COMPARISONS += 1
    return implementation, actions


def bits_of(value: int) -> list[int]:
    return [(value >> index) & 1 for index in range(5)]


def value_plan(address: int, value: int, start_cycle: int, gap: int) -> list[tuple[int, int, int]]:
    return [(address, bit, start_cycle + index * gap)
            for index, bit in enumerate(bits_of(value))]


def run_vectors() -> dict[str, Any]:
    classes: dict[str, Any] = {}

    for value in range(256):
        _implementation, actions = replay("first-write", [(0x8000, value, 7)])
        expected_action = "reset_shift" if value & 0x80 else "shift"
        if actions[0]["action"] != expected_action:
            raise AssertionError(
                f"first-write {value:#04x}: {actions[0]['action']} != {expected_action}")
    classes["first_write_classification"] = 256

    commits = 0
    for address, name, _slot in WINDOWS:
        for value in range(32):
            implementation, actions = replay("commit", value_plan(address, value, 100, 3))
            last = actions[-1]
            if last["action"] != "commit" or last["register"] != name \
                    or last["register_value"] != value:
                raise AssertionError(
                    f"commit {name} {value:#04x}: {last}")
            if serial_model.register_value(implementation, name) != value:
                raise AssertionError(f"commit {name}: register file mismatch")
            commits += 1
    classes["exhaustive_five_write_commits"] = commits

    reset_sequences = 0
    for address, name, _slot in WINDOWS:
        for value in range(32):
            partial = [(address, 1, 10), (address, 1, 13)]
            reset = [(address, 0x80, 16)]
            plan = partial + reset + value_plan(address, value, 20, 3)
            implementation, actions = replay("reset-bit", plan)
            if actions[2]["action"] != "reset_shift":
                raise AssertionError(f"reset-bit: {actions[2]}")
            if actions[-1]["action"] != "commit" or actions[-1]["register_value"] != value:
                raise AssertionError(f"reset-bit commit: {actions[-1]}")
            if implementation.state()["count"] != 0 or implementation.state()["shift"] != 0:
                raise AssertionError("reset-bit: shift state not cleared")
            reset_sequences += 1
    classes["reset_bit_sequences"] = reset_sequences

    implementation, actions = replay("suppression", [
        (0x8000, 1, 10),
        (0x8000, 1, 11),
        (0x8000, 1, 12),
    ])
    if actions[1]["action"] != "suppressed":
        raise AssertionError(f"suppression not detected: {actions[1]}")
    if actions[2]["action"] != "shift":
        raise AssertionError(f"write after suppression not processed: {actions[2]}")
    if implementation.state() != {
            "registers": {"control": 0x0C, "chr_bank_0": 0, "chr_bank_1": 0,
                          "prg_bank": 0},
            "shift": 0b11, "count": 2, "last_write_cycle": 12}:
        raise AssertionError(f"suppression state: {implementation.state()}")
    implementation, actions = replay("suppression-after-reset", [
        (0x8000, 0x80, 10),
        (0x8000, 0x80, 11),
        (0x8000, 0x01, 12),
    ])
    if actions[1]["action"] != "suppressed" or actions[2]["action"] != "shift":
        raise AssertionError("suppression-after-reset sequence mismatch")
    classes["suppression_sequences"] = 3

    implementation, actions = replay("gap-zero", [(0x8000, 1, 10), (0x8000, 1, 10)])
    if actions[1]["action"] != "shift":
        raise AssertionError("same-cycle write should not be suppressed by the +1 rule")
    classes["write_edge_sequences"] = 2

    rng = LCG(RANDOM_SEED)
    addresses = [0x8000, 0x9FFF, 0xA000, 0xBFFF, 0xC000, 0xDFFF, 0xE000, 0xFFFF]
    gaps = [1, 1, 2, 3, 5, 8]
    cycle = 1000
    steps: list[tuple[int, int, int]] = []
    for _index in range(RANDOM_STEPS):
        address = addresses[rng.next() % len(addresses)]
        value = rng.next() & 0xFF
        gap = gaps[rng.next() % len(gaps)]
        cycle += gap
        steps.append((address, value, cycle))
    _implementation, actions = replay("random-mixed", steps)
    classes["random_mixed_writes"] = len(steps)
    classes["random_commits"] = sum(1 for item in actions if item["action"] == "commit")
    classes["random_suppressed"] = sum(1 for item in actions
                                       if item["action"] == "suppressed")
    classes["random_resets"] = sum(1 for item in actions
                                   if item["action"] == "reset_shift")

    return {"classes": classes, "comparisons": COMPARISONS,
            "seed": RANDOM_SEED, "steps": RANDOM_STEPS}


def main() -> int:
    parser = argparse.ArgumentParser(description="P6-02 MMC1 serial protocol gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase6/evidence/P6-02")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES, COMPARISONS
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}
    COMPARISONS = 0

    print("=== P6-02 MMC1 Serial Register Protocol Gate ===", flush=True)
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
        check("control-plane:stage-row", "| P6-02 |" in queue)
        check("control-plane:terminal-reserved",
              f"{TERMINAL_MARKER}=NOT_PROVEN" in queue)
        check("control-plane:compat-reserved",
              f"{COMPAT_MARKER}=NOT_PROVEN" in queue
              and f"{COMPAT_MARKER}=NOT_PROVEN" in state)

        banner("power_on")
        fresh = serial_model.MMC1Serial()
        check("power-on:registers",
              fresh.registers == list(serial_model.POWER_ON_REGISTERS)
              and fresh.state()["registers"] == {
                  "control": 0x0C, "chr_bank_0": 0, "chr_bank_1": 0, "prg_bank": 0})
        check("power-on:shift-state", fresh.shift == 0 and fresh.count == 0
              and fresh.last_write_cycle is None)
        fresh.reset()
        check("power-on:reset-method", fresh.registers == [0x0C, 0, 0, 0]
              and fresh.count == 0)

        banner("register_selection")
        selections = []
        for address in range(0x8000, 0x10000, 0x2000):
            selections.append(serial_model.register_index(address))
        check("selection:window-bases", selections == [0, 1, 2, 3])
        check("selection:window-bounds",
              serial_model.register_index(0x9FFF) == 0
              and serial_model.register_index(0xBFFF) == 1
              and serial_model.register_index(0xDFFF) == 2
              and serial_model.register_index(0xFFFF) == 3)
        check("selection:names", serial_model.REGISTER_NAMES
              == ("control", "chr_bank_0", "chr_bank_1", "prg_bank"))

        banner("differential_vectors")
        vectors = run_vectors()
        check("vectors:comparisons", vectors["comparisons"] > 4000)
        check("vectors:exhaustive-commits",
              vectors["classes"]["exhaustive_five_write_commits"] == 128)
        check("vectors:first-write-classification",
              vectors["classes"]["first_write_classification"] == 256)
        check("vectors:reset-bit", vectors["classes"]["reset_bit_sequences"] == 128)
        check("vectors:random-commits", vectors["classes"]["random_commits"] > 0)
        check("vectors:random-suppressed", vectors["classes"]["random_suppressed"] > 0)
        check("vectors:random-resets", vectors["classes"]["random_resets"] > 0)
        FINDINGS["differential_vectors"] = vectors

        banner("malformed")
        probe = serial_model.MMC1Serial()
        expect_fail("address-below-window",
                    lambda: probe.write(0x7FFF, 0x00, 10),
                    (serial_model.MMC1SerialError,))
        expect_fail("address-above-window",
                    lambda: probe.write(0x10000, 0x00, 10),
                    (serial_model.MMC1SerialError,))
        expect_fail("value-over-byte",
                    lambda: probe.write(0x8000, 0x100, 10),
                    (serial_model.MMC1SerialError,))
        expect_fail("value-negative",
                    lambda: probe.write(0x8000, -1, 10),
                    (serial_model.MMC1SerialError,))
        expect_fail("cycle-negative",
                    lambda: probe.write(0x8000, 0x00, -1),
                    (serial_model.MMC1SerialError,))
        expect_fail("non-integer-address",
                    lambda: probe.write("0x8000", 0x00, 10),
                    (serial_model.MMC1SerialError,))
        expect_fail("boolean-value",
                    lambda: probe.write(0x8000, True, 10),
                    (serial_model.MMC1SerialError,))
        expect_fail("unknown-register-name",
                    lambda: serial_model.register_value(probe, "unmapped"),
                    (serial_model.MMC1SerialError,))
        check("malformed:state-untouched",
              probe.state()["registers"] == {"control": 0x0C, "chr_bank_0": 0,
                                             "chr_bank_1": 0, "prg_bank": 0}
              and probe.count == 0 and probe.last_write_cycle is None)

        banner("published_fixture_writes")
        rom, _metadata = fixture_build.build()
        plan = [
            (0x8000, 1, 10), (0x8000, 1, 13), (0x8000, 1, 16),
            (0x8000, 1, 19), (0x8000, 0, 22),
        ]
        implementation, actions = replay("fixture-control-0x0F", plan)
        check("fixture:control-write",
              actions[-1]["action"] == "commit"
              and serial_model.register_value(implementation, "control") == 0x0F)
        check("fixture:rom-present", len(rom) > 0)

        banner("regressions")
        regressions = []
        for script, extra in (
            ("tools/test_nes_rom_v1.py", []),
            ("tools/test_nes_platform_v1.py", []),
            ("tools/test_phase6_mmc1_inventory_v1.py",
             ["--evidence-dir", ".openrecomp-phase6/scratch/P6-02/regression_p6_01"]),
            ("tools/test_phase6_boundary_v1.py",
             ["--evidence-dir", ".openrecomp-phase6/scratch/P6-02/regression_p6_00"]),
        ):
            record = run_regression(script, extra)
            check(f"regression:{script}:exit", record["returncode"] == 0)
            check(f"regression:{script}:stderr", record["stderr_empty"])
            regressions.append(record)
        FINDINGS["regressions"] = regressions

        banner("evidence_hygiene")
        write_json("serial_protocol.json", {
            "stage": STAGE,
            "claim": "MMC1_SUBSET_V1",
            "power_on": {"control": 0x0C, "shift": 0, "count": 0},
            "suppression_model": "write on the cycle immediately after an MMC1 "
                                 "write is ignored and leaves all state unchanged",
            "vectors": vectors,
        })
        write_json("reference_comparison.json", {
            "stage": STAGE,
            "implementation": ".openrecomp-phase6/src/p6_mmc1_serial_v1.py",
            "reference": ".openrecomp-phase6/src/p6_mmc1_serial_reference_v1.py",
            "comparisons": vectors["comparisons"],
            "mismatches": 0,
            "classes": vectors["classes"],
        })
        write_json("regressions.json", {"stage": STAGE, "regressions": regressions})
        public_bytes = rom
        private_bytes = private_fixture.PRIVATE_ROM.read_bytes()
        for name, data in EVIDENCE_WRITES.items():
            check(f"hygiene:no-public-rom-bytes:{name}", public_bytes not in data)
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
    (EVIDENCE_DIR / "p6_02_tests.json").write_text(
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
