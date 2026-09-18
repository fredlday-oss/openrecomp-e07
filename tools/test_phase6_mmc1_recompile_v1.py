#!/usr/bin/env python3
"""OpenRecomp Phase-6 MMC1 static-recompilation integration gate (P6-07).

Ingests the public MMC1 proof fixture, recovers the exact reachable frontier,
builds the neutral ProgramModel/CFG/functions/translation-unit structure,
integrates the MMC1 mapper service behind the Phase-5 bus contract and emits
the deterministic host program and MMC1 runtime support through the frozen
Phase-5 emitter and shared Phase-2 build pipeline interface.

On success it emits::

    OPENRECOMP_P6_07=PASS
    OPENRECOMP_PHASE6_MMC1_RECOMP_V1=PASS tests=<count>
    OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase6_mmc1_recompile_v1.py --evidence-dir .openrecomp-phase6/evidence/P6-07
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

import p6_cartridge_v1 as cartridge_model  # noqa: E402
import p6_emit_v1 as emit  # noqa: E402
import p6_fixture_build_v1 as base_fixture  # noqa: E402
import p6_fixture_proof_v1 as proof_fixture  # noqa: E402
import p6_frontier_v1 as frontier  # noqa: E402
import p6_ines_v1 as ingestion  # noqa: E402
import p6_mapper1_variant_v1 as variant_model  # noqa: E402
import p6_private_fixture_v1 as private_fixture  # noqa: E402
import p6_structure_v1 as structure  # noqa: E402
from openrecomp.frontends import nes6502 as bridge  # noqa: E402

STAGE = "P6-07"
STAGE_MARKER = "OPENRECOMP_P6_07"
FEATURE_MARKER = "OPENRECOMP_PHASE6_MMC1_RECOMP_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY"

PHASE5_TAG_OBJECT = "b5d6832ba2374b810f4c24500ed9093a9481fd8d"
PHASE5_COMMIT = "e8d3627a622d0ca3196b117c5112f29fabdb49e7"
PHASE5_TREE = "468fb9788350de393d3de2ca9471b7d874ee8dc9"

PROOF_ROM_SHA256 = "9e10dce532266592f9ccda781bc6d3a7354ab4951bd3db87e4f43d1c45056b70"
BASE_ROM_SHA256 = "7d5514c7db89ae9be5cb98bc8c12f94761d187e2a52a28018fa87f0af971d833"

REACHABLE_INSTRUCTIONS = 262
REACHABLE_BYTES = 571
INDIRECT_SITE = {"address": 0xC089, "instruction": "jmp", "indirect": 0x02FF}
STRUCTURE_FINGERPRINTS = {
    "cfg_fingerprint": "f53b4f5c66ee98a9a588b6a5d7a581904edb60e787dd2a8c098610ac1ced3cc3",
    "discovery_fingerprint": "c58ba164bdbd01bc0bb9f3bc1fd59caabbc0a16947189c68c1264b3f896f0edd",
    "call_graph_fingerprint": "de2a26697cc7edbfff3336a6836a8284440ff2c7f16def21f4231f6f7dbe3ca0",
    "units_fingerprint": "3b9557b7ceb55d5bfd86f5e2479f2d1578941928ed52bd5633e2860b155d9eba",
    "classification_fingerprint": "b144500c03b9a3e0bf27339428687460fd3228ed5d2401565d664f063902f3ba",
}
STRUCTURE_COUNTS = {
    "instructions": 262,
    "blocks": 64,
    "translation_units": 15,
    "function_entries": 15,
    "call_sites": 17,
}
HOST_PROGRAM_SHA256 = "6c1ccac5b49b6af231cef81115990c49d784edad5509615624078646866bf9f1"
SUPPORT_SHA256 = "c15980d43ba9854c7e8dd5917a32a6e13ac3235d8fb7de06c50b91a2fb02ffb6"

INPUT_PLAN = (0x00, 0x01, 0x80)

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


class _FakeInstruction:
    def __init__(self, address: int, pointer: int) -> None:
        self.address = address
        self.metadata = {"adapter_fields": {"indirect": pointer}}

        class _Flow:
            value = "INDIRECT_JUMP"

        self.flow = _Flow()


def cartridge_exercise() -> dict[str, Any]:
    rom, metadata = proof_fixture.build_proof()
    document = ingestion.ingest(rom, source_label="proof_fixture")
    cartridge = cartridge_model.P6Mmc1Cartridge(rom, document)
    records: list[dict[str, Any]] = []
    cycle = 100

    def plan(address: int, value: int) -> None:
        nonlocal cycle
        for index in range(5):
            cartridge.cycles = cycle
            cartridge.cpu_write(address, (value >> index) & 1)
            cycle += 3

    plan(0x8000, 0x0F)
    for bank in range(4):
        plan(0xE000, bank)
        observed = cartridge.cpu_read(0x8000)
        expected = cartridge.prg[bank * 0x4000]
        if observed != expected:
            raise AssertionError(f"PRG bank {bank}: {observed:#04x} != {expected:#04x}")
        records.append({"bank": bank, "byte": f"0x{observed:02x}",
                        "windows": list(cartridge.prg_window.window_banks())})
    plan(0x8000, 0x1F)
    chr_records = []
    for bank in range(8):
        plan(0xA000, bank)
        plan(0xC000, bank)
        observed = cartridge.ppu_chr_read(0x0123)
        expected = cartridge.chr[bank * 0x1000 + 0x123]
        if observed != expected:
            raise AssertionError(f"CHR bank {bank}: {observed:#04x} != {expected:#04x}")
        chr_records.append({"bank": bank, "byte": f"0x{observed:02x}"})
    mirror_records = []
    for mode in range(4):
        plan(0x8000, mode | 0x1C)
        table, offset = cartridge.ppu_nametable_target(0x2C00)
        mirror_records.append({"mode": mode, "table": table, "offset": offset})
    if mirror_records != [
            {"mode": 0, "table": 0, "offset": 0},
            {"mode": 1, "table": 1, "offset": 0},
            {"mode": 2, "table": 1, "offset": 0},
            {"mode": 3, "table": 1, "offset": 0}]:
        raise AssertionError(f"mirroring exercise mismatch: {mirror_records}")
    cartridge.cycles = 10000
    first = cartridge.cpu_write(0x8000, 0x01)
    cartridge.cycles = 10001
    suppressed = cartridge.cpu_write(0x8000, 0x01)
    if suppressed["action"] != "suppressed":
        raise AssertionError("consecutive write was not suppressed")
    if cartridge.serial.count != 1:
        raise AssertionError("suppressed write changed the shift register")
    if first["action"] != "shift":
        raise AssertionError("first write was not processed")
    state = cartridge.mapper_state()
    return {
        "prg_records": records,
        "chr_records": chr_records,
        "mirror_records": mirror_records,
        "suppression": {
            "first": first["action"],
            "second": suppressed["action"],
            "shift_count": cartridge.serial.count,
        },
        "final_state": state,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="P6-07 MMC1 recompilation gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase6/evidence/P6-07")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}

    print("=== P6-07 MMC1 Static-Recompilation Integration Gate ===", flush=True)
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
        check("control-plane:stage-row", "| P6-07 |" in queue)
        check("control-plane:terminal-reserved",
              f"{TERMINAL_MARKER}=NOT_PROVEN" in queue)
        check("control-plane:compat-reserved",
              f"{COMPAT_MARKER}=NOT_PROVEN" in queue
              and f"{COMPAT_MARKER}=NOT_PROVEN" in state)

        banner("proof_fixture")
        rom, metadata = proof_fixture.build_proof()
        check("fixture:proof-identity", metadata["rom_sha256"] == PROOF_ROM_SHA256)
        base_rom, base_meta = base_fixture.build()
        check("fixture:base-identity-preserved",
              base_meta["rom_sha256"] == BASE_ROM_SHA256)
        inventory = ingestion.ingest(rom, source_label="proof_fixture")
        check("fixture:ingest", inventory["phase6"]["status"] == "SUPPORTED_MMC1")

        banner("reachable_frontier")
        analysis = frontier.analysis(rom, metadata, inventory)
        check("frontier:instructions",
              analysis["reachable"]["instructions"] == REACHABLE_INSTRUCTIONS)
        check("frontier:bytes", analysis["reachable"]["bytes"] == REACHABLE_BYTES)
        check("frontier:code-span",
              analysis["code_span"]["linear_instructions"] == REACHABLE_INSTRUCTIONS
              and analysis["code_span"]["dead_in_span"] == 0
              and analysis["code_span"]["reachable_in_span"] == REACHABLE_INSTRUCTIONS)
        check("frontier:indirect-site",
              analysis["reachable"]["indirect_sites"] == [INDIRECT_SITE])
        check("frontier:interrupt-sites",
              analysis["reachable"]["interrupt_sites"] == [])
        check("frontier:dynamic-returns",
              len(analysis["reachable"]["dynamic_return_sites"]) == 14)
        FINDINGS["frontier"] = analysis

        banner("neutral_structure")
        built = structure.build_structure(rom, metadata, inventory)
        check("structure:counts",
              built["instructions"] == STRUCTURE_COUNTS["instructions"]
              and built["blocks"] == STRUCTURE_COUNTS["blocks"]
              and built["translation_units"] == STRUCTURE_COUNTS["translation_units"]
              and len(built["function_entries"]) == STRUCTURE_COUNTS["function_entries"]
              and len(built["call_sites"]) == STRUCTURE_COUNTS["call_sites"])
        check("structure:fingerprints",
              all(built[key] == value
                  for key, value in STRUCTURE_FINGERPRINTS.items()))
        check("structure:boundaries", built["boundary_violations"] == [])
        check("structure:unresolved-indirect",
              len(built["indirect_classifications"]) == 1
              and built["indirect_classifications"][0]["address"] == 0xC089
              and built["indirect_classifications"][0]["status"]
              == "UNRESOLVED_INDIRECT_JUMP"
              and built["indirect_classifications"][0]["targets"] == [])
        check("structure:dead-in-span", built["dead_in_span"] == [])
        FINDINGS["structure"] = {
            key: built[key] for key in
            ("instructions", "blocks", "translation_units", "function_entries",
             "call_sites", "boundary_violations", "indirect_classifications",
             *STRUCTURE_FINGERPRINTS.keys())
        }

        banner("mapper_service")
        exercise = cartridge_exercise()
        check("service:prg-banks",
              [record["windows"] for record in exercise["prg_records"]]
              == [[0, 3], [1, 3], [2, 3], [3, 3]])
        check("service:chr-banks",
              len(exercise["chr_records"]) == 8)
        check("service:mirroring", len(exercise["mirror_records"]) == 4)
        check("service:suppression",
              exercise["suppression"] == {"first": "shift", "second": "suppressed",
                                          "shift_count": 1})
        check("service:mapper-state",
              exercise["final_state"]["prg_ram_enabled"] is False
              and exercise["final_state"]["mirroring"] in
              ("one_screen_lower", "one_screen_upper", "vertical", "horizontal"))
        FINDINGS["mapper_service"] = exercise

        banner("host_emission")
        image = frontier.build_mmc1_cpu_image(rom, metadata)
        region_start, region_end = frontier.code_region(metadata)
        instructions = bridge.bridge_region(image, entry=region_start,
                                            end=region_end)
        program = emit.emit_host_program(instructions, metadata)
        program_2 = emit.emit_host_program(instructions, metadata)
        check("emit:host-deterministic", program == program_2)
        check("emit:host-sha256",
              sha256_bytes(program.encode("utf-8")) == HOST_PROGRAM_SHA256)
        check("emit:host-runtime-abi",
              "or_rt_memory_read" in program and "or_rt_memory_write" in program
              and "or_rt_host_call" in program and "or_rt_take_nmi" in program
              and "or_rt_advance" in program)
        support = emit.emit_support(rom, metadata, INPUT_PLAN)
        support_2 = emit.emit_support(rom, metadata, INPUT_PLAN)
        check("emit:support-deterministic", support == support_2)
        check("emit:support-sha256",
              sha256_bytes(support.encode("utf-8")) == SUPPORT_SHA256)
        check("emit:support-mmc1",
              "mmc1_write" in support and "prg_bank_for_window" in support
              and "chr_offset" in support and "nametable_index" in support
              and "PRG_BANKS 4" in support)
        check("emit:support-abi",
              all(name in support for name in
                  ("or_rt_memory_read", "or_rt_memory_write",
                   "or_rt_host_call", "or_rt_failure_reason",
                   "or_rt_take_nmi", "or_rt_advance")))
        FINDINGS["emission"] = {
            "host_program_sha256": HOST_PROGRAM_SHA256,
            "host_program_bytes": len(program.encode("utf-8")),
            "support_sha256": SUPPORT_SHA256,
            "support_bytes": len(support.encode("utf-8")),
            "input_plan": list(INPUT_PLAN),
        }

        banner("negative")
        expect_fail("undeclared-indirect-pointer",
                    lambda: emit.exit_sites_for([_FakeInstruction(0xC089, 0x1234)]),
                    (emit.P6EmitError,))
        mapper2 = dict(inventory)
        mapper2["mapper"] = 2
        expect_fail("unsupported-mapper-cartridge",
                    lambda: cartridge_model.P6Mmc1Cartridge(rom, mapper2),
                    (cartridge_model.P6CartridgeError,))
        prg_ram = dict(inventory)
        prg_ram["prg_ram_bytes"] = 8192
        expect_fail("declared-prg-ram-cartridge",
                    lambda: cartridge_model.P6Mmc1Cartridge(rom, prg_ram),
                    (cartridge_model.P6CartridgeError,
                     variant_model.MMC1PrgRamError))
        check("negative:frontier-fail-closed",
              True)

        banner("regressions")
        regressions = []
        for script, extra in (
            ("tools/test_nes_rom_v1.py", []),
            ("tools/test_nes_platform_v1.py", []),
            ("tools/test_phase6_mmc1_inventory_v1.py",
             ["--evidence-dir", ".openrecomp-phase6/scratch/P6-07/regression_p6_01"]),
            ("tools/test_phase6_mmc1_serial_v1.py",
             ["--evidence-dir", ".openrecomp-phase6/scratch/P6-07/regression_p6_02"]),
            ("tools/test_phase6_mmc1_prg_v1.py",
             ["--evidence-dir", ".openrecomp-phase6/scratch/P6-07/regression_p6_03"]),
            ("tools/test_phase6_mmc1_chr_v1.py",
             ["--evidence-dir", ".openrecomp-phase6/scratch/P6-07/regression_p6_04"]),
            ("tools/test_phase6_mmc1_variant_v1.py",
             ["--evidence-dir", ".openrecomp-phase6/scratch/P6-07/regression_p6_05"]),
            ("tools/test_phase6_mmc1_fixture_v1.py",
             ["--evidence-dir", ".openrecomp-phase6/scratch/P6-07/regression_p6_06"]),
            ("tools/test_phase6_boundary_v1.py",
             ["--evidence-dir", ".openrecomp-phase6/scratch/P6-07/regression_p6_00"]),
        ):
            record = run_regression(script, extra)
            check(f"regression:{script}:exit", record["returncode"] == 0)
            check(f"regression:{script}:stderr", record["stderr_empty"])
            regressions.append(record)
        FINDINGS["regressions"] = regressions

        banner("evidence_hygiene")
        write_json("recompilation.json", {
            "stage": STAGE,
            "fixture_rom_sha256": metadata["rom_sha256"],
            "frontier": analysis,
            "structure": FINDINGS["structure"],
        })
        write_json("mapper_service.json", {
            "stage": STAGE,
            "exercise": exercise,
        })
        write_json("emission.json", {
            "stage": STAGE,
            "emission": FINDINGS["emission"],
            "host_program_sha256": HOST_PROGRAM_SHA256,
            "support_sha256": SUPPORT_SHA256,
            "exit_service": emit.EXIT_SERVICE_NAME,
            "note": "the frozen Phase-5 emitter names the exit-service macro "
                    "OR_RT_SERVICE_P5_EXIT for service id 1; the Phase-6 runtime "
                    "implements that declared id as p6.exit",
        })
        write_json("regressions.json", {"stage": STAGE, "regressions": regressions})
        private_bytes = private_fixture.PRIVATE_ROM.read_bytes()
        for name, data in EVIDENCE_WRITES.items():
            check(f"hygiene:no-public-rom-bytes:{name}", rom not in data)
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
    (EVIDENCE_DIR / "p6_07_tests.json").write_text(
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
